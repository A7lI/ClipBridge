package app.clipbridge;

import com.google.zxing.*;
import com.google.zxing.common.HybridBinarizer;
import com.google.zxing.qrcode.QRCodeReader;
import java.util.*;

final class QrDecoder {
    static String decode(byte[] frame,int width,int height)throws ReaderException{
        PlanarYUVLuminanceSource source=new PlanarYUVLuminanceSource(frame,width,height,0,0,width,height,false);
        QRCodeReader reader=new QRCodeReader();Map<DecodeHintType,Object> hints=new EnumMap<>(DecodeHintType.class);hints.put(DecodeHintType.TRY_HARDER,Boolean.TRUE);
        try{return reader.decode(new BinaryBitmap(new HybridBinarizer(source)),hints).getText();}
        catch(ReaderException first){return reader.decode(new BinaryBitmap(new HybridBinarizer(source.invert())),hints).getText();}
    }
}
