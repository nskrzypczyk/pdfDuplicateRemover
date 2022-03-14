import sys
from typing import List, Tuple, TypedDict, Union
from PyPDF2 import PdfFileReader as PDFFR
from PyPDF2 import PdfFileWriter as PDFW
import textdistance as td
from progress.bar import Bar
from os.path import exists
import fitz

_name_ = "Pdf Duplicate Remover"
__author__ = "Noah Skrzypczyk"
__version__ = "0.1-SNAPSHOT"

"""
PDF Duplicate Remover based on Naive-Fuzzy-Length-Matching
using the extracted pdf text as data-source
.
.
.
DISCLAIMER: The algorithm does not guarantee 100% accuracy.
Known edge cases where equality is detect where there is none:
- 2 pages show the same content. Differences: text color, text highlighting etc.
- 2 pages show the same content, but an object (e.g. an arrow) changes positions
"""

_outfile = "output.pdf"
fitz_pdf = None

def print_help():
    """Prints CLI-Options"""
    print(f"{'#'*20} {_name_} {'#'*20}")
    print("USAGE:\tpython3 pyPDFDuplicateRemover.py [option | file]")
    print("Example:\tpython pyPDFDuplicateRemover.py testFile.pdf -o out.pdf")
    print("Options and arguments:")
    print(f"--help\t\tshow this help message")
    print(f"--version\tprint the version number")
    print(f"-o:\t\tspecify a name for the output file")

def check_file_and_args() -> Union[PDFFR,bool]:
    """Verifies the CLI-Input and options"""
    global _outfile, fitz_pdf
    """
        checks if the file exists and can be read
    """
    output_file_provided:bool = False
    # if no file is provided
    if len(sys.argv)<2: 
        print("Error: Please provide a valid PDF file!")
        print("Pass flag --help for further instructions.")
        return False
    elif "--help" in sys.argv[1:]:
        print_help()
        return False
    elif "--version" in sys.argv[1]:
        print(__version__)
        return False
    elif "-o" in sys.argv:
        if(len(sys.argv)<3):
            print("Error: Please specify a name for the output file!")
            return False
        _outfile = sys.argv[3]
        output_file_provided = True
        if ".pdf" not in _outfile:
            _outfile += ".pdf"

        
    # check if file can be opened
    try:
        fitz_pdf = fitz.open(sys.argv[1])
        reader = PDFFR(open(sys.argv[1],"rb"))
        reader.getNumPages()
        # Update outfile
        if not output_file_provided: _outfile = sys.argv[1][0:sys.argv[1].rindex("/")+1]+_outfile
        new_filename = _outfile
        index = 1
        while(exists(new_filename)):
            new_filename = _outfile.rsplit(".pdf")
            index+=1
            new_filename.insert(1,f"({index})")
            new_filename= "".join(new_filename)+".pdf"
        _outfile = new_filename
        return reader
    except FileNotFoundError:
        print(f"File: '{sys.argv[1]}' cannot be opened")

def extract_images(pagenumber:int)->List[bytes]:
    """ Saves images as Pixmaps """
    global fitz_pdf
    hashes:List[bytes] = []
    img_list = fitz_pdf.getPageImageList(pagenumber)
    for img in img_list:
        xref = img[0]
        pm = fitz.Pixmap(fitz_pdf,xref)
        hashes.append(pm.digest)
    return hashes
   

def extract_text(reader:PDFFR)->Tuple[List, List]:
    """Traverses all pages, extracts the text and returns the content as an string-list

    Args:
        reader (PDFFR): pyPDF2 PdfFileReader instance

    Returns:
        List[str]: content as an string-list
    """
    pages = []
    images = []
    bar = Bar("Extracting Text", max = len(reader.pages))
    for idx, p in enumerate(reader.pages):
        pages.append(p.extractText())
        images.append(extract_images(idx))
        bar.next()
    bar.finish()
    return pages, images

class Result_Dict(TypedDict):
    px:int
    py:int
    sim:float

def analyze(texts:List[str], images:List[bytes])->Union[List[Result_Dict], None]:
    """
    Detects equal pages based on text and image data.
    It uses the Jaccard similarity algorithm from the TextDistance module.
    """
    returndata:List[Result_Dict] = []
    finished = []
    max = len(texts)
    bar = Bar("Analyzing",max=max)
    for i,text in enumerate(texts):
        for k, next_text in enumerate(texts[i+1:], start=i+1):
            if k==i: # skip at equal index
                pass
            else:
                # Check the similarity based on both texts
                sim = td.jaccard.normalized_similarity(text,next_text)
                if sim >0.99:
                    finished.append(f"Pages {i+1} and {k+1} are similar: ({sim}, lenPx: {sum([ord(x) for x in text])}, lenPy:{sum([ord(x) for x in next_text])})")
                    finished.append((images[i], images[k]))
                    # if image data for both pages exists -> check if the lists of bytes are equal
                    if images[i] != [] and images[k] != []:
                        if images[i] == images[k]:
                            returndata.append({"px":i,"py":k,"sim":sim})
                    else:
                        returndata.append({"px":i,"py":k,"sim":sim})
        bar.next()
    bar.finish()
    print(*finished, sep="\n")
    if len(finished) >0:
        print(f"Detected pairs: {len(finished)}")
        return returndata
    else:
        print("No duplicates found.")
        print("No output file produced!")
        return None

def delete_duplicates(reader:PDFFR,data:List[Result_Dict]):
    """Builds the output pdf file based on the analysis results"""

    output = PDFW()
    deleted:List[int] = []
    for e in data: # for every duplicate page in all pairs (x,y)
        if e["py"] not in deleted: # if page y not deleted
            deleted.append(e["py"])
    bar = Bar(f"Building {_outfile}", max=len(reader.pages)-len(deleted))
    for idx,p in enumerate(reader.pages):
        if idx not in deleted:
            output.addPage(p)
            bar.next()
    bar.finish()
        
    with open(_outfile,"wb") as f:
        output.write(f)    

def main()->None:
    """MAIN FUNCTION | STARTINGPOINT"""
    reader = check_file_and_args()
    if not reader: sys.exit(0)

    text, images = extract_text(reader)
    result = analyze(text, images)
    if result is not None: delete_duplicates(reader,result)
    

if __name__ == "__main__":
    main()