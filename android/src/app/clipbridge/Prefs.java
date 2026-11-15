package app.clipbridge;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;
import android.provider.Settings;
import android.util.Base64;
import java.util.UUID;

final class Prefs {
    static SharedPreferences get(Context c) { return c.getSharedPreferences("bridge", Context.MODE_PRIVATE); }
    static boolean enabled(Context c) { return get(c).getBoolean("enabled", false); }
    static boolean paired(Context c) { return get(c).contains("key"); }
    static boolean isKeyboard(Context c) {
        String current = Settings.Secure.getString(c.getContentResolver(), Settings.Secure.DEFAULT_INPUT_METHOD);
        return current != null && current.startsWith(c.getPackageName()+"/");
    }
    static String device(Context c) {
        String value = get(c).getString("device", "");
        if (value.isEmpty()) { value = UUID.randomUUID().toString(); get(c).edit().putString("device", value).apply(); }
        return value;
    }
    static void pair(Context c, String link) throws Exception {
        Uri uri = Uri.parse(link.trim());
        if (!"clipbridge".equals(uri.getScheme())) throw new Exception("Paste the full ClipBridge pairing link from your PC.");
        String host = uri.getHost(); int port = uri.getPort();
        if (host == null || !host.matches("[0-9]{1,3}(\\.[0-9]{1,3}){3}") || port < 1024 || port > 65535)
            throw new Exception("Choose a valid local IPv4 address in the PC app.");
        String[] pieces = host.split("\\."); int[] octets = new int[4];
        for (int i=0;i<4;i++) { octets[i]=Integer.parseInt(pieces[i]); if(octets[i]>255)throw new Exception("Invalid IP address."); }
        if (!(octets[0]==10 || octets[0]==127 || (octets[0]==192 && octets[1]==168)
            || (octets[0]==172 && octets[1]>=16 && octets[1]<=31) || (octets[0]==169 && octets[1]==254)))
            throw new Exception("ClipBridge only connects to a local network address.");
        String key = uri.getQueryParameter("key");
        if (key == null || Base64.decode(key, Base64.URL_SAFE|Base64.NO_WRAP).length!=32)
            throw new Exception("The pairing key is incomplete.");
        get(c).edit().putString("host",host).putInt("port",port).putString("key",key).apply();
    }
}
