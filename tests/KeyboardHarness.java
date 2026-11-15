package app.clipbridge;
import java.util.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;

public class KeyboardHarness {
    private static int checks=0;
    private static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    private static boolean has(WordSuggestions engine,String before,boolean arabic,String expected){List<String> result=engine.suggest(before,arabic,false);boolean found=result.stream().anyMatch(word->WordSuggestions.normalized(word).equals(WordSuggestions.normalized(expected)));if(!found)System.out.println(before+" -> "+result);return found;}
    public static void main(String[] args)throws Exception{
        long loadStart=System.nanoTime();
        Path assets=Paths.get(args[1]);
        WordSuggestions engine=new WordSuggestions(name->Files.newInputStream(assets.resolve(name)));
        System.out.printf("Dictionary load: %.1f ms%n",(System.nanoTime()-loadStart)/1e6);
        check(has(engine,"hel",false,"hello"),"English completion");
        check(has(engine,"Hel",false,"Hello"),"Title case");
        check(engine.suggest("HEL",false,false).contains("HELLO"),"Uppercase");
        check(!engine.suggest("H",false,false).get(0).equals(engine.suggest("H",false,false).get(0).toUpperCase(Locale.ROOT)),"Single capital keeps title case");
        check(has(engine,"مر",true,"مرحبا"),"Arabic completion");
        check(has(engine,"اري",true,"أريد"),"Arabic alef normalization");
        check(has(engine,"مَر",true,"مرحبا"),"Arabic diacritics");
        check(has(engine,"thank ",false,"you"),"English next word");
        check(has(engine,"how are ",false,"you"),"Two-word context");
        check(has(engine,"السلام ",true,"عليكم"),"Arabic next word");
        check(has(engine,"إن شاء ",true,"الله"),"Arabic phrase context");
        check(has(engine,"شنو تسوي ",true,"هسه"),"Iraqi Arabic context");
        check(has(engine,"هسه ",true,"أجي"),"Iraqi Arabic predictions");
        check(has(engine,"where ",false,"are"),"English context");
        check(has(engine,"هل يمكنك ",true,"مساعدتي"),"Arabic context");
        check(has(engine,"hey hel",true,"hello"),"English script with Arabic layout");
        check(has(engine,"مر",false,"مرحبا"),"Arabic script with English layout");
        check(engine.suggest("a".repeat(41),false,false).isEmpty(),"Bounded prefix");
        check(engine.suggest("t",false,false).size()<=3,"Bounded results");
        check(!has(engine,"hello",false,"hello"),"Do not duplicate typed word");
        check(WordSuggestions.prefix("hello wor").equals("wor"),"Prefix at cursor");
        check(WordSuggestions.prefix("نص، مَر").equals("مَر"),"Arabic punctuation and marks");
        check(WordSuggestions.prefix("I don't").equals("don't"),"Contraction");
        check(WordSuggestions.prefix("I don’t").equals("don’t"),"Curly apostrophe");
        check(WordSuggestions.prefix("hello ").isEmpty(),"Space clears prefix");
        check(WordSuggestions.prefix("hello!").isEmpty(),"Punctuation clears prefix");
        check(WordSuggestions.prefix("123hel").equals("hel"),"Numeric boundary");
        check(WordSuggestions.prefix("😀hello").equals("hello"),"Surrogate boundary");
        for(String text:new String[]{"name@example","https://site","example.com","code123","abc/def","x".repeat(41)})check(!WordSuggestions.safeContext(text),"Ignore structured tokens: "+text);
        check(WordSuggestions.safeContext("hello there"),"Normal text allowed");
        engine.learn("hello clipbridge",false);
        check(engine.personalData().contains("clipbridge"),"Custom word learned");
        check(engine.suggest("clipb",false,true).stream().anyMatch(w->w.equalsIgnoreCase("clipbridge")),"Custom word completion");
        check(engine.suggest("hello ",false,true).stream().anyMatch(w->w.equalsIgnoreCase("clipbridge")),"Personal next word");
        check(!engine.suggest("clipb",false,false).stream().anyMatch(w->w.equalsIgnoreCase("clipbridge")),"Personalization off");
        String saved=engine.personalData();engine.clearPersonal();check(engine.personalData().isEmpty(),"Clear personal data");
        engine.restorePersonal(saved);check(engine.personalData().equals(saved),"Restore personal data");
        engine.restorePersonal("malformed data\nw\ten\tbad\tNaN");check(engine.personalData().isEmpty(),"Invalid personal data");
        engine.clearPersonal();
        String[][] typos={{"teh","the"},{"thnaks","thanks"},{"recieve","receive"},{"tomorow","tomorrow"},{"definately","definitely"},{"becuase","because"},{"freind","friend"},{"messgae","message"},{"keybaord","keyboard"},{"langauge","language"},{"helo","hello"},{"woudl","would"},{"مرحباا","مرحبا"},{"السللام","السلام"},{"شكراا","شكرا"},{"مساعده","مساعدة"}};
        int hits=0;
        for(String[] typo:typos){List<String> result=engine.suggest(typo[0],typo[0].charAt(0)>127,false);boolean hit=result.stream().anyMatch(w->WordSuggestions.normalized(w).equals(WordSuggestions.normalized(typo[1])));if(hit)hits++;System.out.println(typo[0]+" -> "+result+(hit?" OK":" MISS"));}
        check(hits==typos.length,"Typo top-3 quality: "+hits+"/"+typos.length);
        check(has(engine,"I recie",false,"receive"),"Misspelled partial word");
        check(has(engine,"Hello. ",false,"Hello"),"Sentence starters");
        check(has(engine,"اين",true,"أين"),"Offer canonical hamza spelling");
        check(has(engine,"باجر ",true,"نشوفك"),"Iraqi next word");
        check(WordSuggestions.normalized("ﻻ").equals("لا"),"Arabic presentation forms");
        check(WordSuggestions.normalized("کَی").equals("كي"),"Persian kaf and yeh");
        check(engine.suggest("I would like ",false,false).get(0).equals("to"),"Longer context ranking");
        engine.learn("meet ClipBridge",false);check(engine.suggest("meet ",false,true).contains("ClipBridge"),"Preserve custom casing");engine.clearPersonal();
        for(int i=0;i<600;i++)engine.learn("word"+letterId(i),false);
        check(engine.personalData().lines().filter(line->line.startsWith("w\t")).count()==500,"Bounded learned vocabulary");engine.clearPersonal();
        ArrayList<Long> times=new ArrayList<>();String[] samples={"t","a","hel","recieve","tomorow","messgae","ال","م","مرحباا","السللام","شنو تسوي ","thank "};
        for(int pass=0;pass<20;pass++)for(String sample:samples){long start=System.nanoTime();engine.suggest(sample,sample.charAt(0)>127,false);times.add(System.nanoTime()-start);}
        Collections.sort(times);System.out.printf("Lookup p50 %.2f ms, p95 %.2f ms, max %.2f ms%n",times.get(times.size()/2)/1e6,times.get((int)(times.size()*.95))/1e6,times.get(times.size()-1)/1e6);
        String source=new String(Files.readAllBytes(Paths.get(args[0])),StandardCharsets.UTF_8);
        String layout=source.substring(source.indexOf("else if(arabic){letters"),source.indexOf("for(String value:last)"));
        for(char letter:"ابتثجحخدذرزسشصضطظعغفقكلمنهويءؤئىة".toCharArray())check(layout.indexOf(letter)>=0,"Missing Arabic letter "+letter);
        System.out.println(checks+" keyboard checks passed");
    }
    private static String letterId(int n){StringBuilder value=new StringBuilder();do{value.append((char)('a'+n%26));n/=26;}while(n>0);return value.toString();}
}
