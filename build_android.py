"""Build a signed APK with the installed Android SDK; Gradle is not required."""
import argparse
import hashlib
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import zipfile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    scratch=args.work.resolve();scratch.mkdir(parents=True,exist_ok=True)
    sdk=Path(os.environ.get('ANDROID_HOME',Path.home()/'AppData/Local/Android/Sdk'))
    java=Path(os.environ.get('JAVA_HOME','C:/Program Files/Android/Android Studio/jbr'))
    tools=sorted((sdk/'build-tools').iterdir(),key=lambda p:tuple(int(s) for s in p.name.split('.') if s.isdigit()))[-1]
    platforms=sorted((sdk/'platforms').iterdir(),key=lambda p:int(p.name.split('-')[1].split('.')[0]))
    android=platforms[-1]/'android.jar'
    zxing=root/'android/libs/zxing-core-3.5.3.jar'
    if hashlib.sha256(zxing.read_bytes()).hexdigest()!='8d8064c1636fdaef7189dd9055c7d59950a8940a12f2293956446ec3c109fd82':
        raise ValueError('ZXing library checksum mismatch')
    env=dict(os.environ,JAVA_HOME=str(java));env['PATH']=str(java/'bin')+os.pathsep+env.get('PATH','')
    def run(*command):
        subprocess.run([str(x) for x in command],check=True,env=env)
    generated=scratch/'generated';generated.mkdir(exist_ok=True)
    classes=scratch/'classes';classes.mkdir(exist_ok=True)
    dex=scratch/'dex';dex.mkdir(exist_ok=True)
    assets=scratch/'assets';assets.mkdir(exist_ok=True)
    shutil.copytree(root/'android/assets',assets,dirs_exist_ok=True)
    for name in ('LICENSE','NOTICE'):shutil.copyfile(root/'licenses/zxing'/name,assets/('ZXing-'+name+'.txt'))
    # Never package old classes (including local test harnesses) into the APK.
    for file in classes.rglob('*.class'):file.unlink()
    for file in dex.glob('*.dex'):file.unlink()
    run(tools/'aapt2.exe','compile','--dir',root/'android/res','-o',scratch/'resources.zip')
    run(tools/'aapt2.exe','link','-o',scratch/'base.apk','-I',android,'--manifest',root/'android/AndroidManifest.xml',
        '--java',generated,'-A',assets,'--min-sdk-version','30','--target-sdk-version','35',scratch/'resources.zip')
    sources=list((root/'android/src').rglob('*.java'))+list(generated.rglob('*.java'))
    run(java/'bin/javac.exe','-encoding','UTF-8','-source','8','-target','8','-bootclasspath',str(android)+os.pathsep+str(tools/'core-lambda-stubs.jar'),'-cp',zxing,'-d',classes,*sources)
    run(java/'bin/java.exe','-cp',tools/'lib/d8.jar','com.android.tools.r8.D8','--lib',android,'--min-api','30','--output',dex,zxing,*classes.rglob('*.class'))
    shutil.copyfile(scratch/'base.apk',scratch/'unsigned.apk')
    with zipfile.ZipFile(scratch/'unsigned.apk','a',compression=zipfile.ZIP_DEFLATED) as archive:
        for file in dex.glob('*.dex'):archive.write(file,file.name)
    run(tools/'zipalign.exe','-f','4',scratch/'unsigned.apk',scratch/'aligned.apk')
    key=scratch/'signing.p12';password_file=scratch/'signing-password.txt'
    if not key.exists():
        password_file.write_text(secrets.token_urlsafe(28),encoding='utf-8')
        run(java/'bin/keytool.exe','-genkeypair','-keystore',key,'-storepass:file',password_file,'-keypass:file',password_file,
            '-alias','clipbridge','-keyalg','RSA','-keysize','3072','-validity','10000','-dname','CN=ClipBridge Local Development','-storetype','PKCS12')
    output=root/'ClipBridge-Android.apk'
    run(java/'bin/java.exe','-jar',tools/'lib/apksigner.jar','sign','--ks',key,'--ks-key-alias','clipbridge','--ks-pass','file:'+str(password_file),'--out',output,scratch/'aligned.apk')
    run(java/'bin/java.exe','-jar',tools/'lib/apksigner.jar','verify','--verbose',output)
    print('Built',output)


if __name__=='__main__':main()
