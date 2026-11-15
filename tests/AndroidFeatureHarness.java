package app.clipbridge;

import java.nio.file.*;
import java.nio.charset.StandardCharsets;

/** Runs production helpers on a JVM; this does not emulate Android UI or MediaStore. */
public class AndroidFeatureHarness {
    private static void check(boolean value){if(!value)throw new AssertionError();}
    public static void main(String[] args)throws Exception{
        if(args.length>0){
            byte[] frame=Files.readAllBytes(Paths.get(args[0]));int width=Integer.parseInt(args[1]),height=Integer.parseInt(args[2]);
            String expected=new String(Files.readAllBytes(Paths.get(args[3])),StandardCharsets.UTF_8);
            check(QrDecoder.decode(frame,width,height).equals(expected));return;
        }
        check(Transfers.safeName("../photo:1.jpg").equals(".._photo_1.jpg"));
        check(Transfers.safeName("CON.txt").equals("_CON.txt"));
        check(Transfers.safeName(".. ").equals("file"));
        check(Transfers.safeName("تقرير.pdf").equals("تقرير.pdf"));
        check(Transfers.safeName("a".repeat(250)+".pdf").endsWith(".pdf"));
        check(ScreenshotWatcher.screenshot("Screenshot_20261104.png","DCIM/Screenshots/"));
        check(ScreenshotWatcher.screenshot("Screen_shot.png","Pictures/"));
        check(!ScreenshotWatcher.screenshot("IMG_20261104.jpg","DCIM/Camera/"));
        System.out.println("Android filename and screenshot classifier checks passed.");
    }
}
