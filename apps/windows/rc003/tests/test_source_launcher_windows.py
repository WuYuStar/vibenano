"""Exercise the source launcher on Windows UNC paths without launching the app."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform == 'win32', 'Windows PowerShell and shortcuts required')
class SourceLauncherWindowsTests(unittest.TestCase):
    def test_unc_source_and_custom_runtime_survive_launch_and_shortcut_arguments(self):
        root = Path(__file__).resolve().parents[1]
        def ps_string(value):
            return "'" + str(value).replace("'", "''") + "'"
        with tempfile.TemporaryDirectory(prefix='rc003-launcher-') as directory:
            directory = Path(directory)
            runtime = directory / 'runtime with spaces'
            runtime.mkdir()
            python = runtime / 'python.exe'
            python.write_bytes(b'')
            pythonw = runtime / 'pythonw.exe'
            pythonw.write_bytes(b'')
            shortcut = directory / 'source launch.lnk'
            script = directory / 'probe.ps1'
            code = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
function Start-Process {
    param([string]$FilePath, [string]$WorkingDirectory, [string[]]$ArgumentList)
    $global:LaunchRecord = @{
        executable = $FilePath; directory = $WorkingDirectory
        arguments = $ArgumentList; pythonpath = $env:PYTHONPATH
        marker = $env:REMOTE_MIC_DEV_SESSION
    }
}
'''
            code += '. ' + ps_string(root / 'build/run-dev.ps1') + ' -PythonExecutable ' + ps_string(python) + '\n'
            code += '. ' + ps_string(root / 'build/install-dev-shortcut.ps1') + ' -PythonExecutable ' + ps_string(python) + ' -ShortcutPath ' + ps_string(shortcut) + '\n'
            code += '$link = (New-Object -ComObject WScript.Shell).CreateShortcut(' + ps_string(shortcut) + ')\n'
            code += r'''
$LaunchRecord.shortcut_arguments = $link.Arguments
$LaunchRecord.shortcut_directory = $link.WorkingDirectory
$LaunchRecord | ConvertTo-Json -Compress
'''
            script.write_text(code, encoding='utf-8-sig')
            powershell = str(Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe')
            result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(script)],
                                    capture_output=True, encoding='utf-8', timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(data['executable'], str(pythonw))
            self.assertEqual(data['directory'], str(root))
            self.assertEqual(data['pythonpath'], str(root / 'src'))
            self.assertNotIn('Microsoft.PowerShell.Core', data['pythonpath'])
            self.assertEqual(data['marker'], '1')
            self.assertEqual(data['arguments'], ['-m', 'ovb_rc003', '--settings', '--remote-mic-dev-session'])
            self.assertIn('-PythonExecutable "' + str(python) + '"', data['shortcut_arguments'])
            self.assertEqual(data['shortcut_directory'], str(root))
