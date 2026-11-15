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
    static final int BG=Ui.BG,PANEL=Ui.PANEL,FG=Ui.FG,ACCENT=Ui.ACCENT,MUTED=Ui.MUTED;
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
    private ViewFlipper pages;
    private Button[] navigation=new Button[3];
    private int selectedTab=0;
    int dp(int n){return Ui.dp(this,n);}
    TextView text(String value,int size,int color){return Ui.text(this,value,size,color);}
    LinearLayout card(LinearLayout parent,String title){return Ui.card(parent,title);}
    Button button(LinearLayout parent,String title,Runnable action){Button b=Ui.button(this,title,action,true);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(46));p.setMargins(0,dp(8),0,0);parent.addView(b,p);return b;}
    private LinearLayout page(){ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setClipToPadding(false);LinearLayout body=Ui.column(this);body.setPadding(0,dp(10),0,dp(8));scroll.addView(body);pages.addView(scroll);return body;}
    private void showTab(int index){selectedTab=index;pages.setDisplayedChild(index);for(int i=0;i<3;i++){navigation[i].setTextColor(i==index?BG:MUTED);navigation[i].setBackground(Ui.key(this,i==index?ACCENT:BG,11));}}
    private void changeSync(){
        if(Prefs.enabled(this)){Prefs.get(this).edit().putBoolean("enabled",false).apply();stopService(new Intent(this,SyncService.class));}
        else{if(!Prefs.paired(this)){showTab(1);toast("Connect your PC first.");return;}if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},11);Prefs.get(this).edit().putBoolean("enabled",true).apply();startForegroundService(new Intent(this,SyncService.class));}refresh();
    }
    private void credits(){try(InputStream in=getAssets().open("suggestions/ATTRIBUTION.txt")){ByteArrayOutputStream bytes=new ByteArrayOutputStream();byte[] buffer=new byte[4096];int n;while((n=in.read(buffer))!=-1)bytes.write(buffer,0,n);TextView label=text(bytes.toString("UTF-8"),13,FG);label.setPadding(dp(18),dp(12),dp(18),dp(12));ScrollView view=new ScrollView(this);view.addView(label);new android.app.AlertDialog.Builder(this).setTitle("Dictionary credits").setView(view).setPositiveButton("Close",null).show();}catch(IOException e){toast("Credits unavailable.");}}
    private Switch setting(LinearLayout parent,String title,String key,boolean fallback){Switch value=new Switch(this);value.setText(title);value.setTextSize(13);value.setTextColor(FG);value.setMinHeight(dp(48));value.setChecked(Prefs.get(this).getBoolean(key,fallback));parent.addView(value);value.setOnCheckedChangeListener((v,on)->Prefs.get(this).edit().putBoolean(key,on).apply());return value;}
    @Override public void onCreate(Bundle state){
        super.onCreate(state);getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);
        if(state!=null){shareHandled=state.getBoolean("shareHandled");String output=state.getString("cameraOutput");if(output!=null)cameraOutput=Uri.parse(output);selectedTab=state.getInt("selectedTab",0);}
        LinearLayout root=Ui.column(this);root.setBackgroundColor(BG);root.setPadding(dp(16),dp(12),dp(16),dp(10));
        root.setOnApplyWindowInsetsListener((v,insets)->{android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars());v.setPadding(dp(16)+bars.left,dp(12)+bars.top,dp(16)+bars.right,dp(10)+bars.bottom);return insets;});
        LinearLayout header=new LinearLayout(this);header.setGravity(Gravity.CENTER_VERTICAL);root.addView(header,new LinearLayout.LayoutParams(-1,dp(52)));
        ImageView logo=new ImageView(this);logo.setImageResource(R.drawable.ic_bridge);header.addView(logo,new LinearLayout.LayoutParams(dp(38),dp(38)));
        TextView heading=text("ClipBridge.",23,FG);heading.setTypeface(null,Typeface.BOLD);LinearLayout.LayoutParams hp=new LinearLayout.LayoutParams(0,-2,1);hp.setMargins(dp(10),0,0,0);header.addView(heading,hp);header.addView(text("0.7.0",12,MUTED));
        pages=new ViewFlipper(this);root.addView(pages,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout share=page();
        LinearLayout phone=card(share,"Phone to phone");phone.addView(text("iPhone + Android · Nearby or online",12,MUTED));button(phone,"Start sharing  ↗",()->startActivity(new Intent(this,PhoneShareActivity.class)));
        LinearLayout computer=card(share,"Computer");status=text("Connect a PC to share here.",12,MUTED);computer.addView(status);toggle=button(computer,"Start syncing",()->changeSync());
        LinearLayout files=Ui.row(computer);Ui.action(files,"Send files",()->{if(!ready())return;try{startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*").putExtra(Intent.EXTRA_ALLOW_MULTIPLE,true).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION),20);}catch(Exception e){toast("No file picker available.");}},false);
        Ui.action(files,"Camera",()->{if(!ready())return;if(checkSelfPermission(Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.CAMERA},22);else takePhoto();},false);
        LinearLayout receive=Ui.row(computer);Ui.action(receive,"Received files",()->startActivity(new Intent(this,FilesActivity.class)),false);Ui.action(receive,"Scan QR",()->scan(),false);
        EditText draft=new EditText(this);Ui.field(draft,"Text for your PC…");draft.setMinLines(2);draft.setGravity(Gravity.TOP);draft.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE);computer.addView(draft);
        LinearLayout sendRow=Ui.row(computer);sendRow.addView(text("20 files · 300 MB",11,MUTED),new LinearLayout.LayoutParams(0,-2,1));Ui.action(sendRow,"Send text",()->{String value=draft.getText().toString();if(value.isEmpty()){toast("Enter some text first.");return;}send(()->new JSONObject().put("kind","text").put("text",value),"text");},true);
        transferStatus=text("",12,ACCENT);computer.addView(transferStatus);
        LinearLayout connect=page();LinearLayout pair=card(connect,"Connect your PC");pair.addView(text("Open ClipBridge on Windows. Use the same Wi-Fi.",13,MUTED));button(pair,"Scan QR code",()->scan());
        LinearLayout linkGroup=Ui.column(this);linkGroup.setVisibility(View.GONE);button(pair,"Use a pairing link",()->linkGroup.setVisibility(linkGroup.getVisibility()==View.GONE?View.VISIBLE:View.GONE));pair.addView(linkGroup);
        link=new EditText(this);Ui.field(link,"clipbridge://…");link.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD);link.setSelectAllOnFocus(true);linkGroup.addView(link);if(getIntent().getData()!=null){link.setText(getIntent().getDataString());linkGroup.setVisibility(View.VISIBLE);selectedTab=1;}
        button(linkGroup,"Save pairing",()->{try{savePair(link.getText().toString());showTab(0);}catch(Exception e){toast(e.getMessage());}});pair.addView(text("Pairing links are private. Share only with your devices.",11,MUTED));
        LinearLayout settings=page();LinearLayout keyboard=card(settings,"Keyboard");keyboard.addView(text("Automatic clipboard sharing with your PC.",12,MUTED));LinearLayout keyboardActions=Ui.row(keyboard);Ui.action(keyboardActions,"Enable",()->startActivity(new Intent(Settings.ACTION_INPUT_METHOD_SETTINGS)),false);Ui.action(keyboardActions,"Select",()->getSystemService(InputMethodManager.class).showInputMethodPicker(),false);
        setting(keyboard,"Key vibration","keyboard_vibration",true);setting(keyboard,"Arabic + English suggestions","keyboard_suggestions",true);setting(keyboard,"Learn words on this phone","keyboard_learning",false);
        LinearLayout words=Ui.row(keyboard);Ui.action(words,"Clear learned words",()->{synchronized(Prefs.class){Prefs.get(this).edit().remove("learned_data").putLong("learned_revision",Prefs.get(this).getLong("learned_revision",0)+1).apply();}toast("Learned words cleared.");},false);Ui.action(words,"Credits",()->credits(),false);
        LinearLayout extras=card(settings,"Extras");screenshotToggle=setting(extras,"Share new screenshots with PC","screenshots",false);screenshotToggle.setOnCheckedChangeListener((v,on)->{Prefs.get(this).edit().putBoolean("screenshots",on).putLong("screenshots_since",System.currentTimeMillis()/1000).apply();if(on&&!ScreenshotWatcher.permitted(this))requestPermissions(new String[]{Build.VERSION.SDK_INT>=33?Manifest.permission.READ_MEDIA_IMAGES:Manifest.permission.READ_EXTERNAL_STORAGE},23);});
        extras.addView(text("Screenshot sharing needs full photo access.",11,MUTED));button(extras,"Allow voice typing",()->requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},10));extras.addView(text("English · 60 sec · Canary model on your PC",11,MUTED));
        button(settings,"Help & privacy",()->new android.app.AlertDialog.Builder(this).setTitle("Quick help").setMessage("PC sharing: same Wi-Fi, syncing on both devices. Enable ClipBridge Keyboard for automatic clipboard access.\n\nPhone sharing: both screens stay open. Online works across networks; Nearby needs the same Wi-Fi/hotspot and one online setup.\n\nFiles: 20 items / 300 MB. Photos paste only in apps that support them.\n\nVoice: download Canary once in Windows (218 MB).\n\nSensitive Android clips are skipped. Learning stays on this phone. For background sync on HyperOS, allow unrestricted battery use.").setPositiveButton("Done",null).show());
        LinearLayout nav=new LinearLayout(this);nav.setPadding(dp(4),dp(4),dp(4),dp(4));nav.setBackground(Ui.shape(this,PANEL,15));String[] titles={"Share","Connect","Settings"};for(int i=0;i<3;i++){final int index=i;navigation[i]=Ui.button(this,titles[i],()->showTab(index),false);LinearLayout.LayoutParams np=new LinearLayout.LayoutParams(0,dp(44),1);if(i>0)np.setMargins(dp(4),0,0,0);nav.addView(navigation[i],np);}root.addView(nav);setContentView(root);showTab(selectedTab);
        if(!shareHandled)handleShare(getIntent());
    }
    private boolean ready(){if(!Prefs.paired(this)){showTab(1);toast("Connect your PC first.");return false;}if(busy){toast("Wait for the current transfer to finish.");return false;}return true;}
    private void savePair(String value)throws Exception{
        // Validate before stopping a working connection.
        Prefs.pair(this,value);boolean running=Prefs.enabled(this);stopService(new Intent(this,SyncService.class));link.setText("");link.setHint("Pairing saved on this phone");
        if(running)handler.postDelayed(()->startForegroundService(new Intent(this,SyncService.class)),300);
        toast("PC connected. Ready to share.");showTab(0);
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
        if(!Prefs.paired(this)){pendingShare=intent;showTab(1);toast("Connect your PC to send this item.");return;}
        shareHandled=true;
        ArrayList<Uri> uris=new ArrayList<>();
        if(Intent.ACTION_SEND_MULTIPLE.equals(action)){ArrayList<Uri> streams=intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM);if(streams!=null)uris.addAll(streams);}
        else {Uri uri=intent.getParcelableExtra(Intent.EXTRA_STREAM);if(uri!=null)uris.add(uri);}
        if(uris.isEmpty()&&intent.getClipData()!=null)for(int i=0;i<intent.getClipData().getItemCount();i++){Uri uri=intent.getClipData().getItemAt(i).getUri();if(uri!=null)uris.add(uri);}
        if(!uris.isEmpty())sendUris(uris,uris.size()==1&&intent.getType()!=null&&intent.getType().startsWith("image/"));
        else {CharSequence value=intent.getCharSequenceExtra(Intent.EXTRA_TEXT);if(value!=null)send(()->new JSONObject().put("kind","text").put("text",value.toString()),"text");else toast("This app did not provide a shareable file or text.");}
    }
    @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);shareHandled=false;if(intent.getData()!=null)link.setText(intent.getDataString());handleShare(intent);}
    @Override protected void onSaveInstanceState(Bundle state){super.onSaveInstanceState(state);state.putInt("selectedTab",selectedTab);state.putBoolean("shareHandled",shareHandled);if(cameraOutput!=null)state.putString("cameraOutput",cameraOutput.toString());}
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
    private void refresh(){status.setText(Prefs.paired(this)?SyncService.status:"Connect a PC to share here.");toggle.setText(Prefs.enabled(this)?"Stop syncing":"Start syncing");}
    private final Runnable tick=new Runnable(){public void run(){refresh();handler.postDelayed(this,1000);}};
    @Override protected void onResume(){super.onResume();if(Prefs.enabled(this)&&Prefs.paired(this)&&!SyncService.running)startForegroundService(new Intent(this,SyncService.class));handler.post(tick);}
    @Override protected void onPause(){handler.removeCallbacks(tick);super.onPause();}
}
