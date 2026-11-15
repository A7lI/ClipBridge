"""Compile the small x64 Explorer command using a portable TinyCC compiler."""
import argparse
from pathlib import Path
import subprocess

parser=argparse.ArgumentParser()
parser.add_argument('--compiler',type=Path,required=True)
parser.add_argument('--output',type=Path)
args=parser.parse_args()
root=Path(__file__).resolve().parent
output=args.output or root/'shell/ClipBridge-Shell.dll'
subprocess.run([str(args.compiler),'-shared',str(root/'shell/clipbridge_shell.c'),str(root/'shell/ole32.def'),'-o',str(output),'-luser32'],check=True)
print('Built',output)
