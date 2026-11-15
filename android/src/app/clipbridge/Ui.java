package app.clipbridge;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.view.Gravity;
import android.widget.*;

final class Ui {
    static final int BG=Color.rgb(8,9,17),PANEL=Color.rgb(20,20,32),FG=Color.rgb(245,243,250),MUTED=Color.rgb(173,166,193),ACCENT=Color.rgb(199,181,255),LINE=Color.rgb(49,43,65);
    static int dp(Context c,int value){return Math.round(value*c.getResources().getDisplayMetrics().density);}
    static GradientDrawable shape(Context c,int color,int radius){GradientDrawable bg=new GradientDrawable();bg.setColor(color);bg.setCornerRadius(dp(c,radius));bg.setStroke(dp(c,1),LINE);return bg;}
    static android.graphics.drawable.Drawable key(Context c,int color,int radius){return new RippleDrawable(ColorStateList.valueOf(0x33c7b5ff),shape(c,color,radius),null);}
    static TextView text(Context c,String value,int size,int color){TextView text=new TextView(c);text.setText(value);text.setTextSize(size);text.setTextColor(color);text.setPadding(0,dp(c,4),0,dp(c,4));return text;}
    static LinearLayout column(Context c){LinearLayout view=new LinearLayout(c);view.setOrientation(1);return view;}
    static LinearLayout card(LinearLayout parent,String title){Context c=parent.getContext();LinearLayout card=column(c);card.setPadding(dp(c,16),dp(c,12),dp(c,16),dp(c,14));card.setBackground(shape(c,PANEL,18));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.setMargins(0,0,0,dp(c,12));parent.addView(card,p);if(!title.isEmpty()){TextView heading=text(c,title,18,FG);heading.setTypeface(null,Typeface.BOLD);card.addView(heading);}return card;}
    static Button button(Context c,String title,Runnable action,boolean primary){Button button=new Button(c);button.setText(title);button.setAllCaps(false);button.setTextSize(13);button.setTypeface(null,Typeface.BOLD);button.setTextColor(primary?BG:FG);button.setMinWidth(0);button.setMinimumWidth(0);button.setMinHeight(dp(c,44));button.setPadding(dp(c,10),0,dp(c,10),0);button.setBackground(key(c,primary?ACCENT:Color.rgb(35,29,49),11));button.setOnClickListener(v->action.run());return button;}
    static LinearLayout row(LinearLayout parent){Context c=parent.getContext();LinearLayout row=new LinearLayout(c);row.setGravity(Gravity.CENTER_VERTICAL);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.setMargins(0,dp(c,7),0,0);parent.addView(row,p);return row;}
    static void action(LinearLayout parent,String title,Runnable run,boolean primary){Context c=parent.getContext();Button button=button(c,title,run,primary);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(c,46),1);if(parent.getChildCount()>0)p.setMargins(dp(c,8),0,0,0);parent.addView(button,p);}
    static void field(EditText field,String hint){Context c=field.getContext();field.setTextColor(FG);field.setHintTextColor(MUTED);field.setTextSize(16);field.setPadding(dp(c,12),dp(c,9),dp(c,12),dp(c,9));field.setBackground(shape(c,BG,11));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.setMargins(0,dp(c,8),0,dp(c,5));field.setLayoutParams(p);field.setImportantForAutofill(android.view.View.IMPORTANT_FOR_AUTOFILL_NO);field.setHint(hint);}
    static String size(long value){if(value<1024)return value+" B";if(value<1024*1024)return Math.round(value/1024.0)+" KB";return String.format(java.util.Locale.ROOT,"%.1f MB",value/(1024.0*1024));}
}
