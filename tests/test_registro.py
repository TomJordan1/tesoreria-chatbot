"""Pruebas locales sin red, credenciales ni dependencias de producción.

Las integraciones se sustituyen al importar; se ejecutan las funciones reales
de servicios.py y main.py con respuestas controladas.
"""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch


RAIZ = Path(__file__).resolve().parents[1]


class AplicacionPrueba:
    def get(self, *args):
        return lambda funcion: funcion

    post = get
    on_event = get


def cargar_modulos():
    sustitutos = {
        "requests": types.SimpleNamespace(get=Mock(), post=Mock()),
        "fastapi": types.SimpleNamespace(FastAPI=AplicacionPrueba, Request=object),
        "dotenv": types.SimpleNamespace(load_dotenv=lambda: None),
        "openai": types.SimpleNamespace(OpenAI=Mock()),
        "msal": types.SimpleNamespace(),
        "generador_pdf": types.SimpleNamespace(generar_comprobante_pdf=Mock()),
    }
    with patch.dict(sys.modules, sustitutos), patch.dict(os.environ, {
        "TELEGRAM_TOKEN": "prueba", "GROQ_API_KEY": "prueba",
    }):
        modulos = []
        for nombre in ("servicios", "main"):
            spec = importlib.util.spec_from_file_location(nombre, RAIZ / f"{nombre}.py")
            modulo = importlib.util.module_from_spec(spec)
            # main importa las funciones reales del módulo servicios de prueba.
            with patch.dict(sys.modules, {m.__name__: m for m in modulos}):
                spec.loader.exec_module(modulo)
            modulos.append(modulo)
    return modulos


servicios, main = cargar_modulos()


def datos_validos(**cambios):
    datos = dict(fecha="16/10/2026", concepto="Materiales", tipo="Compra",
                 ing_eg="Egreso", motivo="Proyecto", acreedor="Tienda",
                 deudor="Ana", estado="Pagado", monto="25.50")
    datos.update(cambios)
    return datos


class ValidacionRegistro(unittest.TestCase):
    def test_rechaza_montos_invalidos_sin_consultar_ni_escribir(self):
        for monto in (None, "", "abc", "25,50", 0, -1, "nan", "inf", True):
            with self.subTest(monto=monto), patch.object(servicios, "obtener_token_ms") as token, patch.object(servicios.requests, "post") as post:
                with self.assertRaises(servicios.ErrorValidacionOperacion):
                    servicios.guardar_en_excel(datos_validos(monto=monto), 100)
                token.assert_not_called()
                post.assert_not_called()

    def test_rechaza_clasificacion_desconocida(self):
        for valor in (None, "", "No determinado", "Compra", 7):
            with self.subTest(valor=valor), self.assertRaises(servicios.ErrorValidacionOperacion):
                servicios.validar_operacion(datos_validos(ing_eg=valor))

    def test_ingreso_y_egreso_conservan_importes_y_columnas(self):
        for clasificacion, ingreso, egreso, saldo in ((" ingreso ", 25.5, 0, "125.50"), ("EGRESO", 0, 25.5, "74.50")):
            with self.subTest(clasificacion=clasificacion), patch.object(servicios, "calcular_codigo_y_nro", return_value=("O16102601", 1)), patch.object(servicios, "obtener_token_ms", return_value="token"), patch.object(servicios.requests, "post") as post:
                resultado = servicios.guardar_en_excel(datos_validos(ing_eg=clasificacion), 100)
                fila = post.call_args.kwargs["json"]["values"][0]
                self.assertEqual(len(fila), 13)
                self.assertEqual(fila[10:13], [ingreso, egreso, None])
                self.assertIsNone(fila[0])
                self.assertEqual(resultado["saldo"], saldo)


class ConsultaSaldo(unittest.TestCase):
    def consultar(self, filas):
        with patch.object(servicios, "obtener_token_ms", return_value="token"), patch.object(servicios.requests, "get", return_value=Mock(status_code=200, json=lambda: {"value": filas})):
            return servicios.obtener_saldo_actual()

    def test_tabla_vacia_y_filas_vacias(self):
        self.assertIsNone(self.consultar([]))
        self.assertIsNone(self.consultar([{"values": [[None] * 13]}]))

    def test_saldo_cero_y_filas_vacias_al_final(self):
        self.assertEqual(self.consultar([{"values": [[None] * 12 + [0]]}, {"values": [[None] * 13]}]), 0)

    def test_registros_sin_saldo_valido_no_son_tabla_vacia(self):
        for saldo in (None, "error", "nan", "inf"):
            with self.subTest(saldo=saldo), self.assertRaises(servicios.ErrorConsultaSaldo):
                self.consultar([{"values": [["codigo"] + [None] * 11 + [saldo]]}])

    def test_error_de_autenticacion(self):
        with patch.object(servicios, "obtener_token_ms", return_value=None), self.assertRaises(servicios.ErrorConsultaSaldo):
            servicios.obtener_saldo_actual()

    def test_error_http_timeout_y_respuesta_invalida(self):
        for respuesta in (Mock(status_code=403, text="error"), Mock(status_code=200, json=lambda: {}), Mock(status_code=200, json=lambda: {"value": None})):
            with self.subTest(respuesta=respuesta), patch.object(servicios, "obtener_token_ms", return_value="token"), patch.object(servicios.requests, "get", return_value=respuesta), self.assertRaises(servicios.ErrorConsultaSaldo):
                servicios.obtener_saldo_actual()
        with patch.object(servicios, "obtener_token_ms", return_value="token"), patch.object(servicios.requests, "get", side_effect=TimeoutError()), self.assertRaises(servicios.ErrorConsultaSaldo):
            servicios.obtener_saldo_actual()


class FlujoRegistro(unittest.TestCase):
    def setUp(self):
        main.user_states.clear()
        self.mensajes = self.enterContext(patch.object(main, "enviar_mensaje"))
        self.saldo = self.enterContext(patch.object(main, "obtener_saldo_actual", return_value=100))
        self.guardar = self.enterContext(patch.object(main, "guardar_en_excel", return_value={**datos_validos(), "codigo": "O16102601"}))
        self.enterContext(patch.object(main.traceback, "print_exc"))
        self.anterior = os.getcwd()
        temporal = self.enterContext(tempfile.TemporaryDirectory(dir=RAIZ))
        os.chdir(temporal)
        self.addCleanup(os.chdir, self.anterior)
        main.user_states["1"] = dict(step="confirmar", datos_procesados=datos_validos(), saldo_previo=100, file_id="foto")

    def enviar(self, texto=None, foto=False):
        mensaje = {"chat": {"id": 1}, "text": texto or ""}
        if foto:
            mensaje["photo"] = [{"file_id": "foto"}]
        request = types.SimpleNamespace()
        async def json():
            return {"message": mensaje}
        request.json = json
        # Este webhook y request.json no suspenden en las pruebas: no hace falta
        # abrir sockets ni iniciar un bucle de eventos para ejecutar la corrutina.
        corrutina = main.telegram_webhook(request)
        try:
            corrutina.send(None)
        except StopIteration:
            return
        finally:
            corrutina.close()
        self.fail("El webhook suspendió inesperadamente durante una prueba sin I/O")

    def test_validacion_conserva_sesion_y_no_consulta_excel(self):
        main.user_states["1"]["datos_procesados"]["monto"] = None
        self.enviar("1")
        self.saldo.assert_not_called()
        self.guardar.assert_not_called()
        self.assertEqual(main.user_states["1"]["step"], "confirmar")

    def test_fallo_de_saldo_antes_de_guardar_conserva_datos(self):
        self.saldo.side_effect = servicios.ErrorConsultaSaldo()
        self.enviar("2")
        self.guardar.assert_not_called()
        self.assertEqual(main.user_states["1"]["step"], "confirmar")

    def test_foto_con_error_de_saldo_permite_reintentar(self):
        main.user_states.clear()
        self.saldo.side_effect = servicios.ErrorConsultaSaldo()
        self.enviar(foto=True)
        self.assertEqual(main.user_states["1"]["step"], "consultar_saldo")
        self.saldo.side_effect = None
        self.enviar("1")
        self.assertEqual(main.user_states["1"]["step"], "elegir_metodo")

    def test_tabla_vacia_sigue_pidiendo_saldo_inicial(self):
        main.user_states.clear()
        self.saldo.return_value = None
        self.enviar(foto=True)
        self.assertEqual(main.user_states["1"]["step"], "pedir_saldo_base")

    def test_guardado_normal_cierra_sesion(self):
        self.enviar("1")
        self.guardar.assert_called_once()
        self.assertNotIn("1", main.user_states)







    def test_escritura_incierta_no_se_repite(self):
        self.guardar.side_effect = TimeoutError()
        self.enviar("1")
        self.enviar("1")
        self.guardar.assert_called_once()
        self.assertEqual(main.user_states["1"]["step"], "verificar_guardado")

    def test_fallo_pdf_no_se_presenta_como_fallo_de_guardado(self):
        with patch.object(main.requests, "get", return_value=Mock(json=lambda: {"ok": False})):
            self.enviar("2")
        self.guardar.assert_called_once()
        self.assertNotIn("1", main.user_states)
        self.assertIn("ya está guardada en Excel", self.mensajes.call_args.args[1])

    def test_envio_pdf_verifica_respuesta_y_limpia_archivos(self):
        for confirmado in (True, False):
            with self.subTest(confirmado=confirmado):
                main.user_states["1"] = dict(step="confirmar", datos_procesados=datos_validos(), saldo_previo=100, file_id="foto")
                def generar(datos, ruta, imagen):
                    Path(ruta).write_bytes(b"pdf de prueba")
                with patch.object(main.requests, "get", side_effect=[Mock(json=lambda: {"ok": True, "result": {"file_path": "foto.jpg"}}), Mock(content=b"imagen")]), patch.object(main, "generar_comprobante_pdf", side_effect=generar), patch.object(main.requests, "post", return_value=Mock(json=lambda: {"ok": confirmado})) as post:
                    self.enviar("2")
                    self.assertEqual(post.call_args.kwargs["timeout"], 30)
                self.assertEqual(list(Path.cwd().iterdir()), [])
                self.assertNotIn("1", main.user_states)
                if not confirmado:
                    self.assertIn("ya está guardada en Excel", self.mensajes.call_args.args[1])




if __name__ == "__main__":
    unittest.main()
