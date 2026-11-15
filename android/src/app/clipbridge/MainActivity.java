package app.clipbridge;

import android.Manifest;
import android.app.Activity;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.*;
import android.provider.Settings;
import android.provider.MediaStore;
import android.net.Uri;
import android.view.*;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.JSONObject;

public class MainActivity extends Activity {
    static final int BG=Color.rgb(16,25,31),PANEL=Color.rgb(27,40,47),FG=Color.rgb(237,244,243),ACCENT=Color.rgb(142,227,195),MUTED=Color.rgb(169,188,192);
    private EditText link;
    private TextView status;
    private Button toggle;
    private TextView transferStatus;
    private Switch screenshotToggle;
    private Uri cameraOutput;
    private Intent pendingShare;
    private boolean shareHandled=false, busy=false;
    private static final ExecutorService transfers=Executors.newSingleThreadExecutor();
    private final Handler handler=new Handler(Looper.getMainLooper());
    int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
    TextView text(String value,int size,int color){TextView t=new TextView(this);t.setText(value);t.setTextSize(size);t.setTextColor(color);t.setPadding(0,dp(6),0,dp(6));return t;}
    LinearLayout card(LinearLayout parent,String title){LinearLayout c=new LinearLayout(this);c.setOrientation(1);c.setPadding(dp(18),dp(14),dp(18),dp(14));c.setBackgroundColor(PANEL);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.setMargins(0,dp(10),0,dp(6));parent.addView(c,p);c.addView(text(title,13,ACCENT));return c;}
    Button button(LinearLayout parent,String title,Runnable action){Button b=new Button(this);b.setText(title);b.setAllCaps(false);b.setTextColor(BG);b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(ACCENT));b.setOnClickListener(v->action.run());parent.addView(b,new LinearLayout.LayoutParams(-1,dp(52)));return b;}
    @Override public void onCreate(Bundle state){
        super.onCreate(state);getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);
        if(state!=null){shareHandled=state.getBoolean("shareHandled");String output=state.getString("cameraOutput");if(output!=null)cameraOutput=Uri.parse(output);}
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(BG);
        LinearLayout root=new LinearLayout(this);root.setOrientation(1);root.setPadding(dp(22),dp(24),dp(22),dp(24));scroll.addView(root);
        scroll.setOnApplyWindowInsetsListener((v,insets)->{android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars());v.setPadding(bars.left,bars.top,bars.right,bars.bottom);return insets;});
        TextView heading=text("ClipBridge",32,FG);heading.setTypeface(null,Typeface.BOLD);root.addView(heading);
        root.addView(text("Copy here. Paste there.",18,ACCENT));
        status=text("Sync is off",14,MUTED);root.addView(status);
        LinearLayout phone=card(root,"PHONE TO PHONE");
        phone.addView(text("Share text, photos and files with iPhone or Android. Use Offline nearby on the same Wi-Fi/hotspot, or Online across different networks. No PC needed. Keep both sharing screens open.",14,FG));
        button(phone,"Phone-to-phone sharing",()->startActivity(new Intent(this,PhoneShareActivity.class)));
        LinearLayout pair=card(root,"01   PAIR WITH YOUR PC");
        pair.addView(text("Keep both devices on the same Wi-Fi. Tap Scan QR code and scan the PC’s code to pair immediately. Other QR codes copy their text straight to your PC.",14,FG));
        button(pair,"Scan QR code",()->scan());
        link=new EditText(this);link.setTextColor(FG);link.setHintTextColor(MUTED);link.setHint("clipbridge://192.168.…");link.setTextSize(13);link.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD);link.setSelectAllOnFocus(true);
        link.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);pair.addView(link,new LinearLayout.LayoutParams(-1,dp(68)));
        if(getIntent().getData()!=null)link.setText(getIntent().getDataString());
        button(pair,"Save pairing",()->{
            try {savePair(link.getText().toString());}
            catch(Exception e){toast(e.getMessage());}
        });
        LinearLayout share=card(root,"02   SEND TO YOUR PC");
        share.addView(text("Send a file, take a photo, or scan a code. You can also choose ClipBridge from another app’s Share menu. The PC must have syncing enabled.",14,FG));
        transferStatus=text("Ready · up to 20 files / 300 MB total",14,ACCENT);share.addView(transferStatus);
        button(share,"Send files",()->{if(!ready())return;try{startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*").putExtra(Intent.EXTRA_ALLOW_MULTIPLE,true).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION),20);}catch(Exception e){toast("No file picker available.");}});
        button(share,"Take photo → PC",()->{if(!ready())return;if(checkSelfPermission(Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.CAMERA},22);else takePhoto();});
        button(share,"Received files",()->startActivity(new Intent(this,FilesActivity.class)));
        screenshotToggle=new Switch(this);screenshotToggle.setText("Automatically copy new screenshots to PC");screenshotToggle.setTextColor(FG);screenshotToggle.setChecked(Prefs.get(this).getBoolean("screenshots",false));share.addView(screenshotToggle);
        screenshotToggle.setOnCheckedChangeListener((v,on)->{
            Prefs.get(this).edit().putBoolean("screenshots",on).putLong("screenshots_since",System.currentTimeMillis()/1000).apply();
            if(on&&!ScreenshotWatcher.permitted(this))requestPermissions(new String[]{Build.VERSION.SDK_INT>=33?Manifest.permission.READ_MEDIA_IMAGES:Manifest.permission.READ_EXTERNAL_STORAGE},23);
            else if(on)toast("Screenshot sync enabled. Keep syncing running on both devices.");
        });
        share.addView(text("Screenshot sync needs full photo access and the background connection. Only newly saved screenshots are sent. Allow all photos when asked; selected photos cannot include future screenshots. You can always Share → ClipBridge instead.",13,MUTED));
        LinearLayout keyboard=card(root,"03   ENABLE THE KEYBOARD");
        keyboard.addView(text("Select ClipBridge Keyboard for automatic sharing of copied text and images from other apps. File sharing, camera, QR and screenshot transfer also work with your usual keyboard.",14,FG));
        button(keyboard,"Enable keyboard",()->startActivity(new Intent(Settings.ACTION_INPUT_METHOD_SETTINGS)));
        button(keyboard,"Select keyboard",()->getSystemService(InputMethodManager.class).showInputMethodPicker());
        Switch vibration=new Switch(this);vibration.setText("Vibrate on keypress");vibration.setTextColor(FG);vibration.setChecked(Prefs.get(this).getBoolean("keyboard_vibration",true));keyboard.addView(vibration);
        vibration.setOnCheckedChangeListener((v,on)->Prefs.get(this).edit().putBoolean("keyboard_vibration",on).apply());
        Switch predictions=new Switch(this);predictions.setText("Arabic and English word suggestions");predictions.setTextColor(FG);predictions.setChecked(Prefs.get(this).getBoolean("keyboard_suggestions",true));keyboard.addView(predictions);
        predictions.setOnCheckedChangeListener((v,on)->Prefs.get(this).edit().putBoolean("keyboard_suggestions",on).apply());
        Switch learning=new Switch(this);learning.setText("Personalize suggestions on this phone");learning.setTextColor(FG);learning.setChecked(Prefs.get(this).getBoolean("keyboard_learning",false));keyboard.addView(learning);
        learning.setOnCheckedChangeListener((v,on)->Prefs.get(this).edit().putBoolean("keyboard_learning",on).apply());
        button(keyboard,"Clear learned words",()->{synchronized(Prefs.class){Prefs.get(this).edit().remove("learned_data").putLong("learned_revision",Prefs.get(this).getLong("learned_revision",0)+1).apply();}toast("Learned words cleared.");});
        keyboard.addView(text("Frequency-ranked Arabic/English completions, spelling alternatives and next-word hints work offline. Tap a suggestion to insert it. Personalization is optional and stores up to 500 words and 1,000 word pairs only on this phone; it is disabled in password and private-learning fields. Hold ا for أ إ آ ٱ and ة for vowel marks. Key vibration also follows Android’s touch-feedback setting.",13,MUTED));
        button(keyboard,"Dictionary credits",()->{try{java.io.InputStream stream=getAssets().open("suggestions/ATTRIBUTION.txt");java.io.ByteArrayOutputStream bytes=new java.io.ByteArrayOutputStream();byte[] buffer=new byte[4096];int n;while((n=stream.read(buffer))!=-1)bytes.write(buffer,0,n);stream.close();TextView credits=text(bytes.toString("UTF-8"),14,FG);credits.setPadding(dp(18),dp(12),dp(18),dp(12));ScrollView view=new ScrollView(this);view.setBackgroundColor(BG);view.addView(credits);new android.app.AlertDialog.Builder(this).setTitle("Dictionary credits").setView(view).setPositiveButton("Close",null).show();}catch(java.io.IOException e){toast("Dictionary credits unavailable.");}});
        keyboard.addView(text("Your password manager keeps your saved logins. Autofill suggestions are supported; nothing needs importing.",13,MUTED));
        LinearLayout voice=card(root,"04   VOICE TYPING");
        voice.addView(text("For voice typing, open ClipBridge on your PC and click Download Canary model once. Then tap the keyboard microphone to record and tap again to transcribe. English · up to 60 seconds.",14,FG));
        button(voice,"Allow microphone for voice typing",()->requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},10));
        LinearLayout sync=card(root,"05   START SYNCING");
        sync.addView(text("Start syncing on the PC too. Clipboard contents and microphone audio use an encrypted connection. No account or cloud service.",14,FG));
        toggle=button(sync,"Start syncing",()->{
            if(Prefs.enabled(this)){Prefs.get(this).edit().putBoolean("enabled",false).apply();stopService(new Intent(this,SyncService.class));}
            else {
                if(!Prefs.paired(this)){toast("Save the PC pairing link first.");return;}
                if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)
                    requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},11);
                Prefs.get(this).edit().putBoolean("enabled",true).apply();startForegroundService(new Intent(this,SyncService.class));
            }
            refresh();
        });
        sync.addView(text("On POCO/HyperOS, allow background activity and set battery use to unrestricted if syncing stops when the screen is off. Open ClipBridge after a reboot if it hasn’t reconnected.",13,MUTED));
        EditText test=new EditText(this);test.setTextColor(FG);test.setHintTextColor(MUTED);test.setHint("Try typing, voice, or paste here…");test.setMinLines(2);test.setGravity(Gravity.TOP);test.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE);sync.addView(test,new LinearLayout.LayoutParams(-1,dp(96)));
        root.addView(text("Photos can paste into apps that accept images. Word suggestions work offline; swipe typing is not available. Android-marked sensitive clipboard items are skipped.",13,MUTED));
        setContentView(scroll);
        if(!shareHandled)handleShare(getIntent());
    }
    private boolean ready(){if(!Prefs.paired(this)){toast("Scan the PC’s pairing QR code first.");return false;}if(busy){toast("Wait for the current transfer to finish.");return false;}return true;}
    private void savePair(String value)throws Exception{
        // Validate before stopping a working connection.
        Prefs.pair(this,value);boolean running=Prefs.enabled(this);stopService(new Intent(this,SyncService.class));link.setText("");link.setHint("Pairing saved on this phone");
        if(running)handler.postDelayed(()->startForegroundService(new Intent(this,SyncService.class)),300);
        toast("Paired. Files, camera and QR sharing are ready. Enable the keyboard and start syncing for automatic clipboard sharing.");
        if(pendingShare!=null){Intent share=pendingShare;pendingShare=null;handleShare(share);}
    }
    private void scan(){if(busy)return;if(checkSelfPermission(Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.CAMERA},21);else startActivityForResult(new Intent(this,ScanActivity.class),21);}
    private void takePhoto(){
        try{
            File folder=new File(new File(getCacheDir(),"camera"),UUID.randomUUID().toString());folder.mkdirs();File file=new File(folder,"camera.jpg");if(!file.createNewFile())throw new IOException();
            cameraOutput=Uri.parse("content://app.clipbridge.files/capture/"+folder.getName()+"/camera.jpg");
            Intent capture=new Intent(MediaStore.ACTION_IMAGE_CAPTURE).putExtra(MediaStore.EXTRA_OUTPUT,cameraOutput).addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_READ_URI_PERMISSION);capture.setClipData(ClipData.newRawUri("Camera output",cameraOutput));
            startActivityForResult(capture,22);
        }catch(Exception e){toast("Could not open the camera. Check camera access.");}
    }
    interface ItemBuilder{JSONObject build()throws Exception;}
    private void send(ItemBuilder builder,String label){
        if(!ready())return;busy=true;transferStatus.setText("Sending "+label+"…");
        transfers.execute(()->{
            try{
                JSONObject item=builder.build();Transfers.send(getApplicationContext(),item);
                runOnUiThread(()->{busy=false;transferStatus.setText("Sent to PC · paste with Ctrl+V");
                    try{if(!item.getString("kind").equals("files"))getSystemService(ClipboardManager.class).setPrimaryClip(Transfers.localClip(this,item));}catch(Exception ignored){}
                    toast("Copied to PC. Press Ctrl+V to paste.");});
            }catch(Exception e){runOnUiThread(()->{busy=false;String message=e.getMessage()==null?"Please try again.":e.getMessage();transferStatus.setText("Not sent · "+message);toast(message);});}
        });
    }
    private void sendUris(ArrayList<Uri> uris,boolean asImage){
        if(uris.isEmpty()){toast("No files selected.");return;}
        if(uris.size()>20){toast("Select up to 20 files.");return;}
        send(()->asImage&&uris.size()==1?Transfers.image(this,uris.get(0)):Transfers.files(this,uris),asImage?"photo":"files");
    }
    private void handleShare(Intent intent){
        String action=intent.getAction();if(!Intent.ACTION_SEND.equals(action)&&!Intent.ACTION_SEND_MULTIPLE.equals(action))return;
        if(!Prefs.paired(this)){pendingShare=intent;transferStatus.setText("Scan your PC’s pairing code, then this item will be sent.");return;}
        shareHandled=true;
        ArrayList<Uri> uris=new ArrayList<>();
        if(Intent.ACTION_SEND_MULTIPLE.equals(action)){ArrayList<Uri> streams=intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM);if(streams!=null)uris.addAll(streams);}
        else {Uri uri=intent.getParcelableExtra(Intent.EXTRA_STREAM);if(uri!=null)uris.add(uri);}
        if(uris.isEmpty()&&intent.getClipData()!=null)for(int i=0;i<intent.getClipData().getItemCount();i++){Uri uri=intent.getClipData().getItemAt(i).getUri();if(uri!=null)uris.add(uri);}
        if(!uris.isEmpty())sendUris(uris,uris.size()==1&&intent.getType()!=null&&intent.getType().startsWith("image/"));
        else {CharSequence value=intent.getCharSequenceExtra(Intent.EXTRA_TEXT);if(value!=null)send(()->new JSONObject().put("kind","text").put("text",value.toString()),"text");else toast("This app did not provide a shareable file or text.");}
    }
    @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);shareHandled=false;if(intent.getData()!=null)link.setText(intent.getDataString());handleShare(intent);}
    @Override protected void onSaveInstanceState(Bundle state){super.onSaveInstanceState(state);state.putBoolean("shareHandled",shareHandled);if(cameraOutput!=null)state.putString("cameraOutput",cameraOutput.toString());}
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] grants){
        super.onRequestPermissionsResult(request,permissions,grants);boolean granted=grants.length>0&&grants[0]==PackageManager.PERMISSION_GRANTED;
        if(request==21&&granted)startActivityForResult(new Intent(this,ScanActivity.class),21);
        else if(request==22&&granted)takePhoto();
        else if(request==23){if(!ScreenshotWatcher.permitted(this)){screenshotToggle.setChecked(false);toast("Automatic screenshots need full photo access. Share → ClipBridge works without it.");}else toast("Screenshot sync enabled. Start syncing to connect.");}
        else if((request==21||request==22)&&!granted)toast("Camera access is needed for photos and QR scanning.");
    }
    @Override protected void onActivityResult(int request,int result,Intent data){
        super.onActivityResult(request,result,data);
        if(request==22){Uri photo=cameraOutput;cameraOutput=null;if(photo==null)return;
            revokeUriPermission(photo,Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_READ_URI_PERMISSION);
            if(result==RESULT_OK)send(()->Transfers.image(this,photo),"photo");
            return;
        }
        if(result!=RESULT_OK)return;
        if(request==21&&data!=null){String value=data.getStringExtra("text");if(value==null)return;
            if(PhoneShareActivity.invitation(value)){startActivity(new Intent(this,PhoneShareActivity.class).putExtra("invitation",value));return;}
            if(value.toLowerCase(Locale.ROOT).startsWith("clipbridge:")){try{savePair(value);}catch(Exception e){toast(e.getMessage());}}
            else send(()->new JSONObject().put("kind","text").put("text",value),"QR text");
        }else if(request==20&&data!=null){ArrayList<Uri> uris=new ArrayList<>();if(data.getClipData()!=null)for(int i=0;i<data.getClipData().getItemCount();i++)uris.add(data.getClipData().getItemAt(i).getUri());else if(data.getData()!=null)uris.add(data.getData());sendUris(uris,false);}
    }
    void toast(String text){Toast.makeText(this,text,Toast.LENGTH_LONG).show();}
    private void refresh(){status.setText(SyncService.status+(Prefs.isKeyboard(this)?"":" · copied-text auto-sync needs ClipBridge Keyboard"));toggle.setText(Prefs.enabled(this)?"Stop syncing":"Start syncing");}
    private final Runnable tick=new Runnable(){public void run(){refresh();handler.postDelayed(this,1000);}};
    @Override protected void onResume(){super.onResume();if(Prefs.enabled(this)&&Prefs.paired(this)&&!SyncService.running)startForegroundService(new Intent(this,SyncService.class));handler.post(tick);}
    @Override protected void onPause(){handler.removeCallbacks(tick);super.onPause();}
}
