import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from ovb_rc003 import key_mapping as km, store_apps_windows as apps, action_executor as executor
from ovb_rc003 import config, mapping_presets, settings_ui

APP_ID="OpenAI.Codex_2p2nqsd0c76g0!App"
TARGET=km.STORE_APP_PREFIX+APP_ID

class StoreAppMappingTests(unittest.TestCase):
    def test_canonical_and_verified_run_dialog_forms_normalize(self):
        for value in (TARGET,'shell:appsfolder\\'+APP_ID,'explorer.exe '+TARGET,'"'+TARGET+'"'):
            self.assertEqual(km.normalize_program_path(value),TARGET)
        action=km.ButtonAction(km.ActionKind.OPEN_PROGRAM,program_path=TARGET)
        self.assertEqual(km.ButtonAction.from_dict(action.to_dict()).program_path,TARGET)

    def test_only_packaged_ids_and_exe_paths_are_accepted(self):
        for value in ('shell:AppsFolder\\'+APP_ID+' & calc.exe',
            'shell:AppsFolder\\'+APP_ID+' --flag','shell:AppsFolder\\..\\bad',
            'shell:AppsFolder\\'+APP_ID+'\nBAD','shell:Downloads',
            'explorer.exe C:\\Windows\\notepad.exe','explorer.exe '+TARGET+'; exit',
            'cmd.exe /c calc.exe', 'shell:AppsFolder\\bad!App'):
            with self.subTest(value=value),self.assertRaises(ValueError):km.normalize_program_path(value)

    def test_all_gestures_save_and_preset_round_trip_without_launch(self):
        for profile in ('xiaomi-rc003','chromecast-remote'):
            original=config.default_key_bindings(profile)
            action=km.ButtonAction(km.ActionKind.OPEN_PROGRAM,program_path=TARGET).to_dict()
            original['bindings']['ok']=action
            original.setdefault('secondary_bindings',{})['ok']={'double_click':action,'long_press':action}
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'mapping.json';config.save_key_bindings(path,original)
                loaded=config.load_key_bindings(path)
                for trigger in km.ButtonTrigger:self.assertEqual(km.button_action_for(loaded,'ok',trigger).program_path,TARGET)
                snap=mapping_presets.snapshot(loaded,profile)
                data=Path(folder)/'data';data.mkdir()
                store=mapping_presets.PresetStore(data);identity=store.create('应用',profile,snap)
                exported=Path(folder)/'preset.json';store.export_file(identity,exported)
                imported=store.import_file(exported,profile)
                self.assertEqual(store.get(imported)['mapping'],snap)

    def test_discovery_filters_invalid_entries_and_deduplicates(self):
        rows=[{'Name':'ChatGPT','AppID':APP_ID},{'Name':'Duplicate','AppID':APP_ID},
              {'Name':'Wrong','AppID':APP_ID+' /bad'},{'Name':'Desktop','AppID':'C:\\app.exe'}]
        with mock.patch.object(apps,'windows_directory',return_value=Path('C:/Windows')), \
             mock.patch.object(apps.subprocess,'run',return_value=mock.Mock(stdout=json.dumps(rows))) as run:
            result=apps.installed_apps()
        self.assertEqual(result,[{'name':'ChatGPT','target':TARGET}])
        self.assertFalse(run.call_args.kwargs.get('shell',False))
        self.assertEqual(run.call_args.kwargs['timeout'],15)

@unittest.skipUnless(__import__('sys').platform=='win32','Windows Shell boundary')
class StoreAppShellTests(unittest.TestCase):
    def launch(self,target):
        captured=[];shell=mock.Mock();ole=mock.Mock();ole.CoInitializeEx.return_value=0
        def execute(pointer):
            info=pointer._obj
            captured.append({'file':info.lpFile,'params':info.lpParameters,'verb':info.lpVerb,'directory':info.lpDirectory})
            return True
        shell.ShellExecuteExW.side_effect=execute
        with mock.patch.object(executor.ctypes,'WinDLL',side_effect=lambda name,**kw:shell if name=='shell32' else ole), \
             mock.patch.object(apps,'windows_directory',return_value=Path('C:/Windows')):
            executor._shell_open_program(target)
        ole.CoUninitialize.assert_called_once()
        return captured[0]

    def test_packaged_app_uses_fixed_system_explorer_and_only_its_id(self):
        result=self.launch(TARGET)
        self.assertEqual(result['file'],str(Path('C:/Windows/explorer.exe')))
        self.assertEqual(result['params'],TARGET)
        self.assertEqual(result['verb'],'open')

    def test_ordinary_exe_still_has_no_command_line_arguments(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'fixture.exe';path.write_bytes(b'fixture')
            result=self.launch(str(path))
        self.assertEqual(result['file'],str(path))
        self.assertIsNone(result['params'])
