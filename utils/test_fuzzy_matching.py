from rapidfuzz import fuzz, process, utils

def find_fuzzy_match(text, tokens):
    toks_list = tokens.split(",")
    print(f"Testing {text}...")
    
    score_cutoff = 80

    # Use rapidfuzz's default preprocessor to normalize strings (lowercase, remove
    # diacritics and punctuation) which matches how token lists are stored.
    # Extract the best score above cutoff or nothing.

    # We don't want partial_ratio here
    # to avoid finding cases when one string is partially included,
    # so cannot use WRatio
    res = process.extractOne(text, toks_list, 
                    scorer=fuzz.WRatio, 
                    processor=utils.default_process, 
                    score_cutoff=score_cutoff)
    print(f"WRatio {res}")
    
    res = process.extractOne(text, toks_list, 
                    scorer=fuzz.QRatio, 
                    processor=utils.default_process, 
                    score_cutoff=score_cutoff)
    print(f"QRatio {res}")

    res = process.extractOne(text, toks_list, 
                    scorer=fuzz.ratio, 
                    processor=utils.default_process, 
                    score_cutoff=score_cutoff)
    print(f"ratio {res}")
    if not res:
        return None
    
    match = res[0]
    return match


if __name__ == "__main__":
    print(find_fuzzy_match("Pelle!","pele"))
    print(find_fuzzy_match("pelē ","pele"))
    print(find_fuzzy_match("komandos muestis ","komandos mosties"))
    print(find_fuzzy_match(" komandos","komandos mosties"))
    print(find_fuzzy_match("komandos dzert ","komandos mosties"))
    print(find_fuzzy_match("mosties ","komandos mosties"))
    print(find_fuzzy_match("jālīmē","ielīmē"))
    print(find_fuzzy_match("komandos guli ","komandos mosties"))
    print(find_fuzzy_match("KOmaNDos mūstjas! "," komaNdos mosties!,komandos guli"))
    print(find_fuzzy_match(" Reportāža.",'Navigātors.,www delfilv,@2 *A %,Sign in,Konference Latvija,Skaties tiešraidē 20.11.,UZZINI VAIRĀK,{ATXIsA,valsts bez atkritumiem 2025,PUNKTS,Delfi V,Ziņas,Bizness,Life,Sports,Kultūra,Auto,Tasty,Delfi TV,Abone,Piesledzies,RUS,Q =,Lawlas / acionaiai:,kvalifikacijas turnīra elites kārtā,fIriīvs,21*51,Daugaviņš hokejista karjeru turpinās Vācijas,klubā,Huskies",20:40,Rinkēvičs: mūsu brivibas gaisma nāk no,rietumiem, nevis austrumiem (30),19*30,Arhīva foto: Kā pirms 90 gadiem tapa Brīvības piemineklis   (2),Mūžībā devies pasaulslavenais fotogrāfs,Ulvis Alberts,19*24,Reportāža: Rigas centru izgaismo lāpu,gājiens (1),18*50,LAV,Latvijas basketbolistes iespaidigi sagrauj,22,41,Igaunijas valstsvienibu,18.11.2025,18*38,B,Usiks atteicies no pasaules čempiona'))