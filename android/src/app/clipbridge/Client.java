package app.clipbridge;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Base64;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.InterfaceAddress;
import java.net.NetworkInterface;
import java.security.MessageDigest;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import javax.crypto.Cipher;
import javax.crypto.Mac;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import org.json.JSONObject;

final class Client {
    static final int LIMIT=24*1024*1024;
    static final SecureRandom RANDOM = new SecureRandom();
    static String b64(byte[] b) { return Base64.encodeToString(b,Base64.NO_WRAP); }
    static byte[] unb64(String s) { return Base64.decode(s,Base64.NO_WRAP); }
    static byte[] authenticate(byte[] key,String message)throws Exception{
        Mac mac=Mac.getInstance("HmacSHA256");mac.init(new SecretKeySpec(key,"HmacSHA256"));
        return mac.doFinal(message.getBytes(StandardCharsets.US_ASCII));
    }
    static boolean rediscover(Context context){
        if(!Prefs.paired(context))return false;
        try(DatagramSocket socket=new DatagramSocket()){
            SharedPreferences p=Prefs.get(context);
            byte[] key=Base64.decode(p.getString("key",""),Base64.URL_SAFE|Base64.NO_WRAP);
            byte[] random=new byte[16];RANDOM.nextBytes(random);String nonce=b64(random);
            byte[] request=new JSONObject().put("nonce",nonce).put("auth",b64(authenticate(key,"CB1 discover "+nonce))).toString().getBytes(StandardCharsets.US_ASCII);
            socket.setBroadcast(true);socket.setSoTimeout(1200);
            LinkedHashSet<InetAddress> broadcasts=new LinkedHashSet<>();broadcasts.add(InetAddress.getByName("255.255.255.255"));
            try{
                for(NetworkInterface network:Collections.list(NetworkInterface.getNetworkInterfaces()))
                    if(network.isUp()&&!network.isLoopback())for(InterfaceAddress address:network.getInterfaceAddresses())
                        if(address.getBroadcast()!=null)broadcasts.add(address.getBroadcast());
            }catch(Exception ignored){}
            for(InetAddress broadcast:broadcasts)try{socket.send(new DatagramPacket(request,request.length,broadcast,48722));}catch(Exception ignored){}
            long deadline=android.os.SystemClock.elapsedRealtime()+2400;
            while(android.os.SystemClock.elapsedRealtime()<deadline){
                try{
                    byte[] buffer=new byte[2048];DatagramPacket packet=new DatagramPacket(buffer,buffer.length);socket.receive(packet);
                    InetAddress sender=packet.getAddress();if(!sender.isSiteLocalAddress()&&!sender.isLinkLocalAddress())continue;
                    JSONObject reply=new JSONObject(new String(packet.getData(),0,packet.getLength(),StandardCharsets.US_ASCII));
                    int port=reply.getInt("port");if(port<1024||port>65535||!nonce.equals(reply.optString("nonce")))continue;
                    byte[] expected=authenticate(key,"CB1 here "+nonce+" "+port);
                    if(!MessageDigest.isEqual(expected,unb64(reply.optString("auth"))))continue;
                    p.edit().putString("host",sender.getHostAddress()).putInt("port",port).apply();return true;
                }catch(java.net.SocketTimeoutException ignored){}catch(Exception ignored){}
            }
        }catch(Exception ignored){}
        return false;
    }
    static byte[] crypt(int mode, byte[] key, byte[] nonce, byte[] raw, String aad) throws Exception {
        Cipher c=Cipher.getInstance("AES/GCM/NoPadding");
        c.init(mode,new SecretKeySpec(key,"AES"),new GCMParameterSpec(128,nonce));
        c.updateAAD(aad.getBytes(StandardCharsets.UTF_8)); return c.doFinal(raw);
    }
    static byte[] read(InputStream input,int limit) throws Exception {
        ByteArrayOutputStream out=new ByteArrayOutputStream(); byte[] buffer=new byte[8192]; int n;
        while((n=input.read(buffer))!=-1) { if(out.size()+n>limit)throw new Exception("Content exceeds size limit."); out.write(buffer,0,n); }
        return out.toByteArray();
    }
    static JSONObject request(Context context,String path,JSONObject value) throws Exception {
        SharedPreferences p=Prefs.get(context);
        if(!Prefs.paired(context))throw new Exception("Pair with your PC first.");
        byte[] key=Base64.decode(p.getString("key",""),Base64.URL_SAFE|Base64.NO_WRAP);
        value.put("time",System.currentTimeMillis()/1000.0).put("device",Prefs.device(context));
        byte[] nonce=new byte[12]; RANDOM.nextBytes(nonce); String requestNonce=b64(nonce);
        byte[] encrypted=crypt(Cipher.ENCRYPT_MODE,key,nonce,value.toString().getBytes(StandardCharsets.UTF_8),"CB1 "+path);
        byte[] body=new JSONObject().put("nonce",requestNonce).put("data",b64(encrypted)).toString().getBytes(StandardCharsets.UTF_8);
        HttpURLConnection conn=(HttpURLConnection)new URL("http",p.getString("host",""),p.getInt("port",48721),path).openConnection();
        try {
            conn.setConnectTimeout(4000); conn.setReadTimeout(path.equals("/v1/transcribe")?150000:60000);
            conn.setInstanceFollowRedirects(false); conn.setRequestMethod("POST"); conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type","application/json"); conn.setFixedLengthStreamingMode(body.length);
            try(java.io.OutputStream output=conn.getOutputStream()){ output.write(body); }
            if(conn.getResponseCode()!=200)throw new Exception("Pairing failed. Check the pairing link and automatic date/time.");
            byte[] reply; try(InputStream input=conn.getInputStream()){ reply=read(input,LIMIT); }
            JSONObject envelope=new JSONObject(new String(reply,StandardCharsets.UTF_8));
            byte[] decoded=crypt(Cipher.DECRYPT_MODE,key,unb64(envelope.getString("nonce")),unb64(envelope.getString("data")),"CB1 reply "+path+" "+requestNonce);
            JSONObject result=new JSONObject(new String(decoded,StandardCharsets.UTF_8));
            if(!result.optBoolean("ok"))throw new Exception(result.optString("error","PC could not complete this request."));
            return result;
        } finally { conn.disconnect(); }
    }
}
