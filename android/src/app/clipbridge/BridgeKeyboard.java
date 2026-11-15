package app.clipbridge;

import android.Manifest;
import android.content.*;
import android.content.pm.PackageManager;
import android.inputmethodservice.InputMethodService;
import android.media.*;
import android.os.*;
import android.text.InputType;
import android.util.Size;
import android.view.*;
import android.view.inputmethod.*;
import android.widget.*;
import android.widget.inline.InlinePresentationSpec;
import java.io.ByteArrayOutputStream;
import java.util.*;
import java.util.concurrent.*;
import org.json.JSONObject;

public class BridgeKeyboard extends InputMethodService {
    private LinearLayout root,keys,suggestions;
    private TextView info;
    private Button mic;
    private boolean shift=false,caps=false,symbols=false,arabic=false,password=false,numeric=false;
    private volatile boolean recording=false,transcribing=false;
    private volatile AudioRecord recorder;
    private volatile int editorGeneration=0;
    private int suggestionGeneration=0;
    private boolean inlineActive=false;
    private final ExecutorService wordWorker=Executors.newSingleThreadExecutor();
    private Future<?> wordJob;
    private WordSuggestions wordEngine;
    private long personalRevision=-1;
    private int wordRequest=0;
    private boolean inputVisible=false;
    private PopupWindow alternatives;
    private final Runnable refreshWords=()->refreshWords();
    private final Runnable repeatDelete=new Runnable(){public void run(){erase();main.postDelayed(this,65);}};
    private String pendingTranscript="";
    private final Handler main=new Handler(Looper.getMainLooper());
    private InputConnection voiceConnection;
    private int voiceGeneration;
    private static final int BOTTOM_LIFT_DP=20;
    int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
    private void settings(){Intent i=new Intent(this,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);startActivity(i);}
    private void message(String value){if(info!=null)info.setText(value);}
    @Override public void onCreate(){setTheme(R.style.ClipBridgeKeyboard);super.onCreate();styleNavigationBar();}
    private void styleNavigationBar(){
        Window window=getWindow().getWindow();if(window==null)return;
        window.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
        window.clearFlags(WindowManager.LayoutParams.FLAG_TRANSLUCENT_NAVIGATION);
        window.setNavigationBarColor(MainActivity.BG);
        window.setNavigationBarDividerColor(MainActivity.BG);
        window.setNavigationBarContrastEnforced(false);
        WindowInsetsController controller=window.getDecorView().getWindowInsetsController();
        if(controller!=null)controller.setSystemBarsAppearance(0,WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS);
    }
    @Override public void onWindowShown(){super.onWindowShown();styleNavigationBar();if(root!=null)root.requestApplyInsets();}
    @Override public boolean onEvaluateFullscreenMode(){return false;}
    @Override public View onCreateInputView(){
        root=new LinearLayout(this);root.setOrientation(1);root.setBackgroundColor(MainActivity.BG);root.setPadding(dp(3),dp(5),dp(3),dp(5+BOTTOM_LIFT_DP));root.setForceDarkAllowed(false);
        root.setOnApplyWindowInsetsListener((view,insets)->{
            // IME navigation controls can overlay the input view. Use the remaining
            // bar/cutout insets, never Type.ime() (which includes this keyboard).
            android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.navigationBars()|WindowInsets.Type.captionBar()|WindowInsets.Type.displayCutout());
            view.setPadding(dp(3)+bars.left,dp(5),dp(3)+bars.right,dp(5+BOTTOM_LIFT_DP)+bars.bottom);
            return insets;
        });
        root.addOnAttachStateChangeListener(new View.OnAttachStateChangeListener(){
            public void onViewAttachedToWindow(View view){view.requestApplyInsets();}
            public void onViewDetachedFromWindow(View view){}
        });
        LinearLayout toolbar=new LinearLayout(this);toolbar.setGravity(Gravity.CENTER_VERTICAL);
        info=new TextView(this);info.setTextColor(MainActivity.ACCENT);info.setTextSize(12);info.setPadding(dp(9),0,0,0);info.setText("ClipBridge · Wi-Fi");
        toolbar.addView(info,new LinearLayout.LayoutParams(0,dp(40),1));
        mic=key(toolbar,"Mic",1,()->voice());mic.setContentDescription("Start or stop voice typing");
        key(toolbar,"Paste",1,()->paste());key(toolbar,"⚙",.7f,()->settings());root.addView(toolbar);
        HorizontalScrollView strip=new HorizontalScrollView(this);strip.setHorizontalScrollBarEnabled(false);
        suggestions=new LinearLayout(this);suggestions.setGravity(Gravity.CENTER_VERTICAL);strip.addView(suggestions);root.addView(strip,new LinearLayout.LayoutParams(-1,dp(48)));
        keys=new LinearLayout(this);keys.setOrientation(1);root.addView(keys);drawKeys();return root;
    }
    private Button key(LinearLayout parent,String text,float weight,Runnable click){
        Button b=new Button(this);b.setText(text);b.setTextSize(text.codePointCount(0,text.length())>3?13:20);b.setAllCaps(false);b.setTextColor(MainActivity.FG);
        b.setPadding(0,0,0,0);b.setMinWidth(0);b.setMinimumWidth(0);b.setMinHeight(0);b.setMinimumHeight(0);
        // Emit feedback explicitly so the app toggle also controls long presses.
        b.setHapticFeedbackEnabled(false);
        b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(MainActivity.PANEL));
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(47),weight);p.setMargins(dp(1),dp(1),dp(1),dp(1));parent.addView(b,p);b.setOnClickListener(v->{feedback(b);click.run();});return b;
    }
    private void feedback(View view){if(Prefs.get(this).getBoolean("keyboard_vibration",true))view.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP,HapticFeedbackConstants.FLAG_IGNORE_VIEW_SETTING);}
    private LinearLayout row(){LinearLayout r=new LinearLayout(this);r.setGravity(Gravity.CENTER);r.setLayoutDirection(View.LAYOUT_DIRECTION_LTR);keys.addView(r,new LinearLayout.LayoutParams(-1,-2));return r;}
    private void letters(String[] values){LinearLayout r=row();for(String value:values)letter(r,value);}
    private void letter(LinearLayout r,String value){
        Button b=key(r,value,1,()->type(value));String variants=variants(value);
        if(!variants.isEmpty()){b.setContentDescription(value+"; hold for "+variants);b.setOnLongClickListener(v->{feedback(b);showAlternatives(b,variants);return true;});}
    }
    static String variants(String value){
        switch(value){case "ا":return "أ إ آ ٱ";case "و":return "ؤ";case "ي":return "ى ئ";case "ه":return "ة";case "ك":return "ک گ";case "ب":return "پ";case "ج":return "چ";case "ف":return "ڤ";case "لا":return "لأ لإ لآ";case "ة":return "َ ُ ِ ْ ّ ً ٌ ٍ ٰ";default:return "";}
    }
    private void showAlternatives(View anchor,String values){
        dismissAlternatives();LinearLayout choices=new LinearLayout(this);choices.setPadding(dp(4),dp(4),dp(4),dp(4));choices.setBackgroundColor(MainActivity.BG);choices.setLayoutDirection(View.LAYOUT_DIRECTION_LTR);
        alternatives=new PopupWindow(choices,Math.min(dp(values.split(" ").length*48),getResources().getDisplayMetrics().widthPixels-dp(8)),dp(58),true);
        alternatives.setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(MainActivity.BG));alternatives.setOutsideTouchable(true);alternatives.setElevation(dp(8));
        for(String option:values.split(" "))key(choices,option,1,()->{type(option);dismissAlternatives();});
        alternatives.showAsDropDown(anchor,0,-anchor.getHeight()-dp(58));
    }
    private void dismissAlternatives(){if(alternatives!=null){alternatives.dismiss();alternatives=null;}}
    private void drawKeys(){
        if(keys==null)return;keys.removeAllViews();
        if(numeric){letters(new String[]{"1","2","3"});letters(new String[]{"4","5","6"});letters(new String[]{"7","8","9"});LinearLayout r=row();key(r,".",1,()->type("."));key(r,"0",1,()->type("0"));backspace(r);}
        else {
            letters("1 2 3 4 5 6 7 8 9 0".split(" "));
            if(symbols){letters(new String[]{"@","#","$","%","&","*","-","+","(",")"});letters(new String[]{"!","\"","'",":",";","/","?","_","=","~"});}
            else if(arabic){letters("ض ص ث ق ف غ ع ه خ ح ج د".split(" "));letters("ش س ي ب ل ا ت ن م ك ط".split(" "));}
            else {letters((shift?"Q W E R T Y U I O P":"q w e r t y u i o p").split(" "));letters((shift?"A S D F G H J K L":"a s d f g h j k l").split(" "));}
            LinearLayout third=row();Button shiftKey=key(third,caps?"⇧⇧":shift?"⬆":"⇧",1.4f,()->{shift=!shift;caps=false;drawKeys();});
            shiftKey.setOnLongClickListener(v->{feedback(v);caps=!caps;shift=caps;drawKeys();return true;});
            String[] last=symbols?new String[]{"[","]","{","}","<",">","\\","|"}:arabic?"ئ ء ؤ ر لا ى ة و ز ظ ذ".split(" "):(shift?"Z X C V B N M":"z x c v b n m").split(" ");
            for(String value:last)letter(third,value);backspace(third);
        }
        LinearLayout bottom=row();key(bottom,symbols?"ABC":"?123",1.4f,()->{symbols=!symbols;numeric=false;drawKeys();});
        Button globe=key(bottom,arabic?"EN":"ع",.9f,()->{arabic=!arabic;Prefs.get(this).edit().putBoolean("arabic",arabic).apply();drawKeys();refreshWords();});
        globe.setContentDescription("Switch English or Arabic; hold to change keyboard");globe.setOnLongClickListener(v->{feedback(v);getSystemService(InputMethodManager.class).showInputMethodPicker();return true;});
        key(bottom,",",.7f,()->type(arabic?"،":","));key(bottom,arabic?"مسافة":"space",3.8f,()->type(" "));key(bottom,".",.7f,()->type("."));key(bottom,enterLabel(),1.5f,()->enter());
    }
    private void backspace(LinearLayout r){
        Button b=key(r,"⌫",1.5f,()->erase());b.setContentDescription("Backspace");
        b.setOnTouchListener((v,event)->{if(event.getAction()==MotionEvent.ACTION_DOWN)main.postDelayed(repeatDelete,450);if(event.getAction()==MotionEvent.ACTION_UP||event.getAction()==MotionEvent.ACTION_CANCEL)main.removeCallbacks(repeatDelete);return false;});
    }
    private void erase(){InputConnection c=getCurrentInputConnection();if(c==null)return;CharSequence selected=c.getSelectedText(0);if(selected!=null&&selected.length()>0)c.commitText("",1);else c.deleteSurroundingTextInCodePoints(1,0);scheduleWords();}
    private void type(String text){InputConnection c=getCurrentInputConnection();String before=c!=null&&wordsAllowed()&&" .,!?،؟".contains(text)?beforeCursor(c):null;if(c!=null&&c.commitText(text,1)&&before!=null)learnWord(before);scheduleWords();if(shift&&!caps&&!text.equals(" ")){shift=false;drawKeys();}}
    private void cancelWords(){wordRequest++;main.removeCallbacks(refreshWords);if(wordJob!=null)wordJob.cancel(true);}
    private void scheduleWords(){cancelWords();if(inputVisible)main.postDelayed(refreshWords,35);}
    private boolean wordsAllowed(){EditorInfo e=getCurrentInputEditorInfo();if(e==null||password||numeric||!Prefs.get(this).getBoolean("keyboard_suggestions",true))return false;int variation=e.inputType&InputType.TYPE_MASK_VARIATION;return (e.inputType&InputType.TYPE_MASK_CLASS)==InputType.TYPE_CLASS_TEXT&&(e.inputType&InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS)==0&&variation!=InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS&&variation!=InputType.TYPE_TEXT_VARIATION_WEB_EMAIL_ADDRESS&&variation!=InputType.TYPE_TEXT_VARIATION_URI&&variation!=InputType.TYPE_TEXT_VARIATION_FILTER;}
    private boolean personalizationAllowed(){EditorInfo e=getCurrentInputEditorInfo();return wordsAllowed()&&e!=null&&(e.imeOptions&EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING)==0&&Prefs.get(this).getBoolean("keyboard_learning",false);}
    private String beforeCursor(InputConnection c){
        CharSequence selected=c.getSelectedText(0);if(selected!=null&&selected.length()>0)return null;
        CharSequence after=c.getTextAfterCursor(1,0);if(after!=null&&after.length()>0&&WordSuggestions.isWord(Character.codePointAt(after,0)))return null;
        CharSequence before=c.getTextBeforeCursor(256,0);if(before==null)return null;
        String value=before.toString();return WordSuggestions.safeContext(value)?value:null;
    }
    private WordSuggestions engine()throws java.io.IOException{
        if(wordEngine==null)wordEngine=new WordSuggestions(name->getAssets().open(name));
        long revision=Prefs.get(this).getLong("learned_revision",0);
        if(revision!=personalRevision){wordEngine.restorePersonal(Prefs.get(this).getString("learned_data",""));personalRevision=revision;}
        return wordEngine;
    }
    private void learnWord(String before){
        if(!personalizationAllowed())return;final boolean language=arabic;final long revision=Prefs.get(this).getLong("learned_revision",0);
        wordWorker.execute(()->{try{
            WordSuggestions engine=engine();synchronized(Prefs.class){
                if(!Prefs.get(this).getBoolean("keyboard_learning",false)||revision!=Prefs.get(this).getLong("learned_revision",0))return;
                engine.learn(before,language);Prefs.get(this).edit().putString("learned_data",engine.personalData()).apply();
            }
        }catch(java.io.IOException ignored){}});
    }
    private void refreshWords(){
        if(suggestions==null||inlineActive||!inputVisible)return;suggestions.removeAllViews();if(!wordsAllowed())return;InputConnection c=getCurrentInputConnection();if(c==null)return;
        String before=beforeCursor(c);if(before==null)return;int generation=editorGeneration,request=++wordRequest;boolean language=arabic,personalize=personalizationAllowed();
        wordJob=wordWorker.submit(()->{try{
            List<String> words=engine().suggest(before,language,personalize);
            if(Thread.currentThread().isInterrupted())return;
            main.post(()->{if(request==wordRequest&&generation==editorGeneration&&c==getCurrentInputConnection()&&inputVisible&&!inlineActive&&wordsAllowed()&&before.equals(beforeCursor(c)))showWords(words,before,c,generation,request);});
        }catch(java.io.IOException ignored){}});
    }
    private void showWords(List<String> words,String before,InputConnection c,int generation,int request){
        suggestions.removeAllViews();String prefix=WordSuggestions.prefix(before);
        for(String word:words){
            Button b=key(suggestions,word,1,()->{
                if(request!=wordRequest||generation!=editorGeneration||getCurrentInputConnection()!=c||!wordsAllowed()||!before.equals(beforeCursor(c)))return;
                CharSequence after=c.getTextAfterCursor(1,0);String suffix=after==null||after.length()==0?" ":"";
                c.beginBatchEdit();try{if((prefix.isEmpty()||c.deleteSurroundingText(prefix.length(),0))&&c.commitText(word+suffix,1))learnWord(before.substring(0,before.length()-prefix.length())+word);}finally{c.endBatchEdit();}scheduleWords();
            });b.setTextSize(16);b.setSingleLine(true);b.setEllipsize(android.text.TextUtils.TruncateAt.END);b.setLayoutParams(new LinearLayout.LayoutParams(dp(118),dp(44)));b.setContentDescription("Insert suggestion "+word);
        }
    }
    @Override public void onUpdateSelection(int oldStart,int oldEnd,int newStart,int newEnd,int candidatesStart,int candidatesEnd){super.onUpdateSelection(oldStart,oldEnd,newStart,newEnd,candidatesStart,candidatesEnd);scheduleWords();}
    private String enterLabel(){EditorInfo e=getCurrentInputEditorInfo();if(e==null)return "↵";int a=e.imeOptions&EditorInfo.IME_MASK_ACTION;return a==EditorInfo.IME_ACTION_GO?"Go":a==EditorInfo.IME_ACTION_SEARCH?"Search":a==EditorInfo.IME_ACTION_NEXT?"Next":a==EditorInfo.IME_ACTION_SEND?"Send":a==EditorInfo.IME_ACTION_DONE?"Done":"↵";}
    private void enter(){InputConnection c=getCurrentInputConnection();EditorInfo e=getCurrentInputEditorInfo();if(c==null||e==null)return;int a=e.imeOptions&EditorInfo.IME_MASK_ACTION;if((e.imeOptions&EditorInfo.IME_FLAG_NO_ENTER_ACTION)==0&&a!=EditorInfo.IME_ACTION_NONE&&a!=EditorInfo.IME_ACTION_UNSPECIFIED)c.performEditorAction(a);else c.commitText("\n",1);}
    private void paste(){if(!pendingTranscript.isEmpty()){type(pendingTranscript);pendingTranscript="";message("Dictation inserted");return;}InputConnection c=getCurrentInputConnection();if(c!=null&&!c.performContextMenuAction(android.R.id.paste))message("This field does not accept this clipboard item");}
    @Override public void onStartInput(EditorInfo info,boolean restarting){
        super.onStartInput(info,restarting);editorGeneration++;cancelWords();cancelRecording();suggestionGeneration++;inlineActive=false;dismissAlternatives();main.removeCallbacks(repeatDelete);
        int variation=info.inputType&InputType.TYPE_MASK_VARIATION,kind=info.inputType&InputType.TYPE_MASK_CLASS;
        password=(kind==InputType.TYPE_CLASS_TEXT&&(variation==InputType.TYPE_TEXT_VARIATION_PASSWORD||variation==InputType.TYPE_TEXT_VARIATION_WEB_PASSWORD||variation==InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD))||(kind==InputType.TYPE_CLASS_NUMBER&&variation==InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        numeric=kind==InputType.TYPE_CLASS_NUMBER||kind==InputType.TYPE_CLASS_PHONE;symbols=false;shift=false;caps=false;arabic=Prefs.get(this).getBoolean("arabic",false);
        if(suggestions!=null)suggestions.removeAllViews();drawKeys();if(mic!=null)mic.setEnabled(!password&&!transcribing);
    }
    @Override public void onStartInputView(EditorInfo info,boolean restarting){super.onStartInputView(info,restarting);inputVisible=true;scheduleWords();message(password?"Password manager autofill":pendingTranscript.isEmpty()?"ClipBridge · "+(SyncService.connected?"PC connected":"PC offline"):"Tap Paste to insert last dictation");}
    @Override public void onFinishInput(){editorGeneration++;inputVisible=false;cancelWords();cancelRecording();suggestionGeneration++;inlineActive=false;main.removeCallbacks(repeatDelete);dismissAlternatives();if(suggestions!=null)suggestions.removeAllViews();super.onFinishInput();}
    @Override public void onWindowHidden(){inputVisible=false;cancelWords();cancelRecording();main.removeCallbacks(repeatDelete);dismissAlternatives();super.onWindowHidden();}

    @Override public InlineSuggestionsRequest onCreateInlineSuggestionsRequest(Bundle extras){
        // AndroidX inline UI v1 bundle format; rendered by the user's autofill provider.
        // ClipBridge neither reads nor stores the saved credential suggestions.
        Bundle style=new Bundle();style.putBoolean("style_v1",true);
        Bundle styles=new Bundle();String version="androidx.autofill.inline.ui.version:v1";
        styles.putStringArrayList("androidx.autofill.inline.ui.version:key",new ArrayList<>(Arrays.asList(version)));styles.putBundle(version,style);
        InlinePresentationSpec spec=new InlinePresentationSpec.Builder(new Size(dp(40),dp(40)),new Size(dp(300),dp(46))).setStyle(styles).build();
        return new InlineSuggestionsRequest.Builder(Arrays.asList(spec)).setMaxSuggestionCount(6).build();
    }
    @Override public boolean onInlineSuggestionsResponse(InlineSuggestionsResponse response){
        if(suggestions==null)onCreateInputView();suggestions.removeAllViews();int generation=++suggestionGeneration;inlineActive=!response.getInlineSuggestions().isEmpty();if(!inlineActive)refreshWords();
        for(InlineSuggestion item:response.getInlineSuggestions())item.inflate(this,new Size(-2,dp(44)),getMainExecutor(),view->{if(view!=null&&generation==suggestionGeneration&&suggestions!=null)suggestions.addView(view);});
        return !response.getInlineSuggestions().isEmpty();
    }

    private void voice(){
        if(recording){recording=false;message("Transcribing on your PC…");return;}
        if(transcribing)return;
        if(password){message("Voice typing is disabled in password fields");return;}
        if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){message("Allow microphone in ClipBridge settings first");settings();return;}
        if(!SyncService.connected||!SyncService.voiceReady){message("Start the PC companion and select your Canary model");return;}
        voiceConnection=getCurrentInputConnection();voiceGeneration=editorGeneration;recording=true;mic.setText("Stop");message("Listening · tap Stop · 60 seconds max");
        new Thread(()->record(),"ClipBridgeVoice").start();
    }
    private void cancelRecording(){recording=false;AudioRecord current=recorder;if(current!=null)try{current.stop();}catch(Exception ignored){}if(mic!=null&&!transcribing)mic.setText("Mic");}
    private void record(){
        int generation=voiceGeneration;InputConnection connection=voiceConnection;
        try{
            int size=Math.max(4096,AudioRecord.getMinBufferSize(16000,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT));
            AudioRecord audio=new AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION,16000,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT,size);
            recorder=audio;ByteArrayOutputStream buffer=new ByteArrayOutputStream();
            try{
                if(audio.getState()!=AudioRecord.STATE_INITIALIZED)throw new Exception("Microphone is unavailable");
                if(!recording||generation!=editorGeneration)return;
                audio.startRecording();byte[] bytes=new byte[2048];
                while(recording&&buffer.size()<16000*2*60){int n=audio.read(bytes,0,Math.min(bytes.length,16000*2*60-buffer.size()));if(n<0){if(!recording)break;throw new Exception("Microphone read failed");}buffer.write(bytes,0,n);}
            }finally{recording=false;try{audio.stop();}catch(Exception ignored){}audio.release();recorder=null;}
            if(generation!=editorGeneration)return;
            if(buffer.size()<6400)throw new Exception("Recording was too short");
            transcribing=true;main.post(()->{mic.setText("…");mic.setEnabled(false);message("Transcribing locally on your PC…");});
            JSONObject result=Client.request(this,"/v1/transcribe",new JSONObject().put("audio",Client.b64(buffer.toByteArray())));String transcript=result.optString("text","").trim();
            main.post(()->{if(transcript.isEmpty())message("No speech detected. Try again.");else if(generation==editorGeneration&&connection==getCurrentInputConnection()){connection.commitText(transcript+" ",1);message("Dictation inserted");}else{pendingTranscript=transcript;message("Tap Paste to insert last dictation");}});
        }catch(Exception e){main.post(()->message(e.getMessage()==null?"Voice typing failed. Try again.":e.getMessage()));}
        finally{recording=false;transcribing=false;main.post(()->{if(mic!=null){mic.setText("Mic");mic.setEnabled(!password);}});}
    }
    @Override public void onDestroy(){editorGeneration++;cancelWords();wordWorker.shutdownNow();cancelRecording();main.removeCallbacksAndMessages(null);super.onDestroy();}
}
