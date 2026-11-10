"""Exercise model downloads through the real settings/QML, without networking."""
import json,os,subprocess,sys,tempfile,unittest
from tests.test_hid_runtime_upgrade_qml import _SETUP

_PROBE=_SETUP+r'''
from PySide6.QtCore import QMetaObject
from unittest import mock
find(window, "tabBar").setProperty("currentIndex", 2)
for retired in ("faster_whisper","paraformer_streaming","qwen3_asr"):
    controller._replace_voice_program_settings({"provider":retired})
    assert controller.voiceProgramNanoSelected
controller.refreshModelDownloads()
render(window,app)
assert len(controller.modelDownloadItems)==1
nano=find(window,"downloadModel_fun_asr_nano")
assert nano.property("visible") and nano.property("enabled")
with mock.patch.object(controller._model_download_manager,"start",return_value=True) as start:
    assert QMetaObject.invokeMethod(nano,"clicked")
    start.assert_called_once_with("fun_asr_nano","nano")
root=m.model_downloads.cache_root(controller._config_root/"models","fun_asr_nano")
m.model_downloads._Reporter(root,"nano").emit("downloading","正在下载",filename="model.gguf",done=512,total=1024,force=True)
controller.refreshModelDownloads()
render(window,app)
row=controller.modelDownloadItems[0]
assert row["busy"] and row["percent"]==50
assert not nano.property("enabled")
assert find(window,"modelProgress_fun_asr_nano").property("value")==50
m.model_downloads._Reporter(root,"nano").emit("failed","下载失败，请检查网络和磁盘空间后重试",force=True)
controller.refreshModelDownloads()
render(window,app)
assert nano.property("text")=="重试" and nano.property("enabled")
assert not [str(w) for w in warnings]
window.hide()
m._shutdown_diagnostics_workers()
print(json.dumps({"rows":1,"progress":50,"retry":True,"warnings":[]}))
'''

class ModelDownloadQmlTests(unittest.TestCase):
    def test_download_buttons_progress_and_retry(self):
        with tempfile.TemporaryDirectory() as root:
            env=dict(os.environ,LOCALAPPDATA=root,QT_QPA_PLATFORM='offscreen')
            r=subprocess.run([sys.executable,'-B','-c',_PROBE],env=env,capture_output=True,text=True,timeout=90)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
