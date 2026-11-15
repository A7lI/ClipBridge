package app.clipbridge;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.text.Normalizer;
import java.util.*;

/** Offline frequency/context ranker. Instances are confined to the suggestion worker. */
public final class WordSuggestions {
    public interface Source { InputStream open(String name) throws IOException; }
    private static final int MAX_WORD=40, MAX_VISITS=35000;
    private final Dictionary english,arabic;
    private final Map<String,List<String>> phrases=new HashMap<>();
    private final LinkedHashMap<String,Integer> learned=new LinkedHashMap<>(), pairs=new LinkedHashMap<>();

    public WordSuggestions(Source source) throws IOException {
        english=new Dictionary(source.open("suggestions/en.txt"));
        arabic=new Dictionary(source.open("suggestions/ar.txt"));
        try(BufferedReader reader=reader(source.open("suggestions/phrases.txt"))){
            String line;while((line=reader.readLine())!=null){
                if(line.startsWith("#")||line.trim().isEmpty())continue;
                String[] words=line.trim().split(" +");
                for(int i=1;i<words.length;i++){
                    addPhrase(normalized(words[i-1]),words[i]);
                    if(i>1)addPhrase(normalized(words[i-2])+" "+normalized(words[i-1]),words[i]);
                }
            }
        }
    }
    private static BufferedReader reader(InputStream input){return new BufferedReader(new InputStreamReader(input,StandardCharsets.UTF_8));}
    private void addPhrase(String context,String word){List<String> list=phrases.get(context);if(list==null){list=new ArrayList<>();phrases.put(context,list);}if(!list.contains(word))list.add(word);}
    public static boolean isWord(int cp){return Character.isLetter(cp)||Character.getType(cp)==Character.NON_SPACING_MARK||cp=='\''||cp==0x2019;}
    public static String prefix(String before){
        int i=before.length();while(i>0){int cp=before.codePointBefore(i);if(!isWord(cp))break;i-=Character.charCount(cp);}
        while(i<before.length()&&(before.charAt(i)=='\''||before.charAt(i)=='’'))i++;
        return before.substring(i);
    }
    public static boolean safeContext(String before){
        if(prefix(before).length()>MAX_WORD)return false;
        int start=before.length();while(start>0&&!Character.isWhitespace(before.charAt(start-1)))start--;
        String token=before.substring(start);
        return token.indexOf('@')<0&&token.indexOf('/')<0&&token.indexOf(':')<0&&
            (prefix(before).isEmpty()||token.indexOf('.')<0)&&token.codePoints().noneMatch(Character::isDigit);
    }
    static String normalized(String value){
        StringBuilder out=new StringBuilder();
        for(char c:Normalizer.normalize(value,Normalizer.Form.NFKC).toLowerCase(Locale.ROOT).toCharArray()){
            if((c>=0x064B&&c<=0x065F)||c==0x0670||c==0x0640)continue;
            if(c=='أ'||c=='إ'||c=='آ'||c=='ٱ')c='ا';
            else if(c=='ی')c='ي';else if(c=='ک')c='ك';else if(c=='’')c='\'';
            out.append(c);
        }return out.toString();
    }
    private static boolean hasArabic(String word){for(int i=0;i<word.length();i++)if(Character.UnicodeBlock.of(word.charAt(i))==Character.UnicodeBlock.ARABIC)return true;return false;}
    private static List<String> previousWords(String before){
        ArrayList<String> words=new ArrayList<>();int end=before.length();
        while(end>0&&words.size()<2){
            char c=before.charAt(end-1);if(c=='.'||c=='!'||c=='?'||c=='؟'||c=='\n')break;
            if(!isWord(c)){end--;continue;}
            String word=prefix(before.substring(0,end));if(word.isEmpty())break;
            words.add(0,normalized(word));end-=word.length();
        }return words;
    }
    private static boolean sentenceStart(String before){String trimmed=before.trim();return trimmed.isEmpty()||".!?؟".indexOf(trimmed.charAt(trimmed.length()-1))>=0||before.endsWith("\n");}
    private static String casing(String word,String prefix,boolean capitalize){
        if(hasArabic(word))return word;
        if(prefix.length()>1&&prefix.equals(prefix.toUpperCase(Locale.ROOT)))return word.toUpperCase(Locale.ROOT);
        if(capitalize||(!prefix.isEmpty()&&Character.isUpperCase(prefix.charAt(0))))return Character.toUpperCase(word.charAt(0))+word.substring(1);
        return word.equals("i")?"I":word;
    }
    public List<String> suggest(String before,boolean useArabic,boolean personalize){
        if(Thread.currentThread().isInterrupted())return Collections.emptyList();
        String typed=prefix(before);if(typed.length()>MAX_WORD)return Collections.emptyList();
        String query=normalized(typed);if(!typed.isEmpty())useArabic=hasArabic(typed);
        Dictionary dictionary=useArabic?arabic:english;String lang=useArabic?"ar":"en";
        String context=before.substring(0,before.length()-typed.length());List<String> previous=previousWords(context);
        String one=previous.isEmpty()?"":previous.get(previous.size()-1),two=String.join(" ",previous);
        Map<String,Candidate> candidates=new HashMap<>();
        if(!query.isEmpty()){
            dictionary.prefix(query,candidates);
            // Frequent valid words keep completion priority; rare corpus spellings
            // (including misspellings) can still receive spelling alternatives.
            if(query.length()>=3&&(!dictionary.contains(query)||dictionary.frequency(query)<35))dictionary.fuzzy(query,candidates);
            if(useArabic&&query.length()>2){
                char last=query.charAt(query.length()-1);char alternate=last=='ه'?'ة':last=='ة'?'ه':last=='ي'?'ى':last=='ى'?'ي':'\0';
                if(alternate!='\0'){String form=query.substring(0,query.length()-1)+alternate;String word=dictionary.spelling(form);if(word!=null)put(candidates,word,dictionary.frequency(form)+25);}
            }
        }
        addContext(candidates,phrases.get(one),query,44,dictionary);
        if(previous.size()==2)addContext(candidates,phrases.get(two),query,65,dictionary);
        if(query.isEmpty()&&candidates.isEmpty())addContext(candidates,Arrays.asList(useArabic?new String[]{"السلام","مرحبا","أنا"}:new String[]{"I","Hello","Thanks"}),query,20,dictionary);
        if(personalize){
            for(Map.Entry<String,Integer> item:learned.entrySet()){
                String[] parts=item.getKey().split("\t");if(!parts[0].equals(lang))continue;
                String word=parts[1],key=normalized(word);if(!query.isEmpty()&&key.startsWith(query))put(candidates,word,70+item.getValue()*2);
            }
            for(Map.Entry<String,Integer> item:pairs.entrySet()){
                String[] parts=item.getKey().split("\t");if(parts[0].equals(lang)&&parts[1].equals(one)&&normalized(parts[2]).startsWith(query))put(candidates,parts[2],100+item.getValue()*2);
            }
        }
        List<Candidate> ranked=new ArrayList<>(candidates.values());
        ranked.removeIf(candidate->candidate.word.equalsIgnoreCase(typed));
        ranked.sort((a,b)->{int order=Double.compare(b.score,a.score);return order!=0?order:a.word.compareTo(b.word);});
        List<String> result=new ArrayList<>();boolean capitalize=!useArabic&&sentenceStart(context);
        for(Candidate candidate:ranked){result.add(casing(candidate.word,typed,capitalize));if(result.size()==3)break;}
        return result;
    }
    private static void addContext(Map<String,Candidate> candidates,List<String> words,String query,double bonus,Dictionary dictionary){
        if(words==null)return;int position=0;
        for(String word:words){String key=normalized(word);if(key.startsWith(query)){
            double score=dictionary.frequency(key)+30+bonus-Math.min(position,12)*2;
            Candidate existing=candidates.get(key);if(existing!=null)existing.score=Math.max(existing.score,score);else put(candidates,word,score);
        }position++;}
    }
    private static void put(Map<String,Candidate> out,String word,double score){String key=normalized(word);Candidate old=out.get(key);if(old==null||score>old.score)out.put(key,new Candidate(word,score));}
    private static final class Candidate {final String word;double score;Candidate(String word,double score){this.word=word;this.score=score;}}

    public void learn(String before,boolean useArabic){
        String word=prefix(before);if(word.length()<2||word.length()>32||word.codePoints().anyMatch(cp->!isWord(cp)))return;
        useArabic=hasArabic(word);String lang=useArabic?"ar":"en";
        Dictionary dictionary=useArabic?arabic:english;String canonical=dictionary.spelling(normalized(word));
        if(canonical!=null)word=canonical;
        increment(learned,lang+"\t"+word,500);
        List<String> previous=previousWords(before.substring(0,before.length()-prefix(before).length()));
        if(!previous.isEmpty())increment(pairs,lang+"\t"+previous.get(previous.size()-1)+"\t"+word,1000);
    }
    private static void increment(LinkedHashMap<String,Integer> map,String key,int max){Integer old=map.remove(key);map.put(key,Math.min(20,old==null?1:old+1));while(map.size()>max)map.remove(map.keySet().iterator().next());}
    public void clearPersonal(){learned.clear();pairs.clear();}
    public String personalData(){StringBuilder out=new StringBuilder();for(Map.Entry<String,Integer> e:learned.entrySet())out.append("w\t").append(e.getKey()).append('\t').append(e.getValue()).append('\n');for(Map.Entry<String,Integer> e:pairs.entrySet())out.append("b\t").append(e.getKey()).append('\t').append(e.getValue()).append('\n');return out.toString();}
    public void restorePersonal(String data){
        clearPersonal();for(String line:data.split("\n")){String[] p=line.split("\t");try{
            if(p.length==4&&p[0].equals("w")&&validWord(p[2]))learned.put(p[1]+"\t"+p[2],Math.max(1,Math.min(20,Integer.parseInt(p[3]))));
            if(p.length==5&&p[0].equals("b")&&validWord(p[2])&&validWord(p[3]))pairs.put(p[1]+"\t"+p[2]+"\t"+p[3],Math.max(1,Math.min(20,Integer.parseInt(p[4]))));
        }catch(NumberFormatException ignored){}if(learned.size()>500||pairs.size()>1000){clearPersonal();break;}}
    }
    private static boolean validWord(String value){return !value.isEmpty()&&value.length()<=40&&value.codePoints().allMatch(WordSuggestions::isWord);}

    /** Sorted prefix lookup plus compact trie for bounded Damerau-Levenshtein search. */
    private static final class Dictionary {
        private final String[] words,normalized;
        private final double[] frequencies;
        private char[] character=new char[262144];
        private int[] child=new int[262144],sibling=new int[262144],terminal=new int[262144];
        private int nodes=1;
        Dictionary(InputStream input)throws IOException{
            Map<String,String> spellings=new TreeMap<>();Map<String,Long> counts=new HashMap<>();
            try(BufferedReader reader=reader(input)){String line;while((line=reader.readLine())!=null){
                if(line.startsWith("#")||line.isEmpty())continue;int split=line.lastIndexOf(' ');if(split<1)continue;
                String word=line.substring(0,split),key=normalized(word);long count=Long.parseLong(line.substring(split+1));
                if(!validWord(word))continue;
                if(!counts.containsKey(key)||count>counts.get(key)){spellings.put(key,word);counts.put(key,count);}
            }}
            int size=spellings.size();words=new String[size];normalized=new String[size];frequencies=new double[size];int i=0;
            for(Map.Entry<String,String> e:spellings.entrySet()){normalized[i]=e.getKey();words[i]=e.getValue();frequencies[i]=Math.log10(1+counts.get(e.getKey()))*10;insert(e.getKey(),i++);}
        }
        private void insert(String word,int index){int node=0;for(char c:word.toCharArray()){
            int next=child[node],last=0;while(next!=0&&character[next]!=c){last=next;next=sibling[next];}
            if(next==0){next=nodes++;if(nodes>=child.length){int size=child.length*2;child=Arrays.copyOf(child,size);sibling=Arrays.copyOf(sibling,size);terminal=Arrays.copyOf(terminal,size);character=Arrays.copyOf(character,size);}character[next]=c;if(last==0)child[node]=next;else sibling[last]=next;}node=next;
        }terminal[node]=index+1;}
        boolean contains(String key){return Arrays.binarySearch(normalized,key)>=0;}
        String spelling(String key){int i=Arrays.binarySearch(normalized,key);return i<0?null:words[i];}
        double frequency(String key){int i=Arrays.binarySearch(normalized,key);return i<0?25:frequencies[i];}
        void prefix(String query,Map<String,Candidate> out){int start=Arrays.binarySearch(normalized,query);if(start<0)start=-start-1;
            for(int i=start;i<words.length&&normalized[i].startsWith(query);i++)put(out,words[i],frequencies[i]+30-Math.min(16,normalized[i].length()-query.length())*1.4);
        }
        void fuzzy(String query,Map<String,Candidate> out){int[] row=new int[query.length()+1];for(int i=0;i<row.length;i++)row[i]=i;int[] visits={0};int distance=query.length()>=6?2:1;
            for(int n=child[0];n!=0&&visits[0]<MAX_VISITS;n=sibling[n])search(n,query,row,null,'\0',distance,visits,out);
        }
        private void search(int node,String query,int[] previous,int[] beforePrevious,char previousChar,int max,int[] visits,Map<String,Candidate> out){
            if(++visits[0]>MAX_VISITS||Thread.currentThread().isInterrupted())return;
            char c=character[node];int[] row=new int[previous.length];row[0]=previous[0]+1;int min=row[0];
            for(int i=1;i<row.length;i++){
                int cost=query.charAt(i-1)==c?0:1;
                row[i]=Math.min(previous[i]+1,Math.min(row[i-1]+1,previous[i-1]+cost));
                if(beforePrevious!=null&&i>1&&c==query.charAt(i-2)&&previousChar==query.charAt(i-1))row[i]=Math.min(row[i],beforePrevious[i-2]+1);
                min=Math.min(min,row[i]);
            }
            int index=terminal[node]-1,distance=row[row.length-1];
            if(index>=0&&distance<=max)put(out,words[index],frequencies[index]+20-distance*18-(query.charAt(0)==normalized[index].charAt(0)?0:6));
            // A typo can occur before the user finishes the word, e.g. recie -> receive.
            if(query.length()>=4&&row[0]==query.length()&&distance==1){
                for(int n=child[node];n!=0&&visits[0]<MAX_VISITS;n=sibling[n])collect(n,1,visits,out);
            }
            if(min<=max)for(int n=child[node];n!=0&&visits[0]<MAX_VISITS;n=sibling[n])search(n,query,row,previous,c,max,visits,out);
        }
        private void collect(int node,int tail,int[] visits,Map<String,Candidate> out){
            if(tail>8||++visits[0]>MAX_VISITS||Thread.currentThread().isInterrupted())return;
            int index=terminal[node]-1;if(index>=0)put(out,words[index],frequencies[index]+2-tail*2.5);
            for(int n=child[node];n!=0&&visits[0]<MAX_VISITS;n=sibling[n])collect(n,tail+1,visits,out);
        }
    }
}
