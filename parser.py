import xml.etree.ElementTree as ET
import re
import subprocess
import os
import sys
import math
import csv
import pandas as pd
sys.setrecursionlimit(3000)

SRC_NS = 'http://www.srcML.org/srcML/src'
POS_NS = 'http://www.srcML.org/srcML/position'
SRC_CPP = 'http://www.srcML.org/srcML/cpp'

NS = {'src': SRC_NS, 'pos': POS_NS}
NEWLINE_RE = re.compile(r'\r\n?|\n')

C_LIB_FUNCTIONS = ["abort","abs","acos","asctime","asctime_r","asin","assert","atan","atan2","atexit","atof","atoi","atol","bsearch","btowc","calloc","catclose","catgets","catopen","ceil","clearerr","clock","cos","cosh","ctime","ctime64","ctime_r","ctime64_r","difftime","difftime64","div","erf","erfc","exit","exp","fabs","fclose","fdopen","feof","ferror","fflush","fgetc","fgetpos","fgets","fgetwc","fgetws","fileno","floor","fmod","fopen","fprintf","fputc","fputs","fputwc","fputws","fread","free","freopen","frexp","fscanf","fseek","fsetpos","ftell","fwide","fwprintf","fwrite","fwscanf","gamma","getc","getchar","getenv","gets","getwc","getwchar","gmtime","gmtime64","gmtime_r","gmtime64_r","hypot","isalnum","isalpha","isascii","isblank","iscntrl","isdigit","isgraph","islower","isprint","ispunct","isspace","isupper","iswalnum","iswalpha","iswblank","iswcntrl","iswctype","iswdigit","iswgraph","iswlower","iswprint","iswpunct","iswspace","iswupper","iswxdigit","isxdigit","j0","j1","jn","labs","ldexp","ldiv","localeconv","localtime","localtime64","localtime_r","localtime64_r","log","log10","longjmp","malloc","mblen","mbrlen","mbrtowc","mbsinit","mbsrtowcs","mbstowcs","mbtowc","memchr","memcmp","memcpy","memmove","memset","mktime","mktime64","modf","nextafter","nextafterl","nexttoward","nexttowardl","nl_langinfo","perror","pow","printf","putc","putchar","putenv","puts","putwc","putwchar","qsort","quantexpd32","quantexpd64","quantexpd128","quantized32","quantized64","quantized128","samequantumd32","samequantumd64","samequantumd128","raise","rand","rand_r","realloc","regcomp","regerror","regexec","regfree","remove","rename","rewind","scanf","setbuf","setjmp","setlocale","setvbuf","signal","sin","sinh","snprintf","sprintf","sqrt","srand","sscanf","strcasecmp","strcat","strchr","strcmp","strcoll","strcpy","strcspn","strerror","strfmon","strftime","strlen","strncasecmp","strncat","strncmp","strncpy","strpbrk","strptime","strrchr","strspn","strstr","strtod","strtod32","strtod64","strtod128","strtof","strtok","strtok_r","strtol","strtold","strtoul","strxfrm","swprintf","swscanf","system","tan","tanh","time","time64","tmpfile","tmpnam","toascii","tolower","toupper","towctrans","towlower","towupper","ungetc","ungetwc","va_arg","va_copy","va_end","va_start","vfprintf","vfscanf","vfwprintf","vfwscanf","vprintf","vscanf","vsprintf","vsnprintf","vsscanf","vswprintf","vswscanf","vwprintf","vwscanf","wcrtomb","wcscat","wcschr","wcscmp","wcscoll","wcscpy","wcscspn","wcsftime","wcslen","wcslocaleconv","wcsncat","wcsncmp","wcsncpy","wcspbrk","wcsptime","wcsrchr","char *ctime64_r(const time64_t *time, char *buf);","wcsspn","wcsstr","wcstod","wcstod32","wcstod64","wcstod128","wcstof","wcstok","wcstol","wcstold","wcstombs","wcstoul","wcsxfrm","wctob","wctomb","wctrans","wctype","wcwidth","wmemchr","wmemcmp","wmemcpy","wmemmove","wmemset","wprintf","wscanf","y0","y1","yn"]
C_LIB_STREAMS = ["stderr", "stdout"]
C_RESERVED_KEYWORDS = ["auto", "const", "int", "short", "struct", "unsigned", "double", "float", "break", "continue", "long", "signed", "switch", "void", "else", "for", "case", "default", "register", "sizeof", "typedef", "volatile", "enum", "goto", "char", "do", "return", "static", "union", "while", "extern", "if"]

def _get_name(element):
    name = element.find('src:name', NS)
    if name is not None:
        name = ''.join(i.strip() for i in name.itertext())
    return name

def _get_name_from_nested_name(name):
    if name is not None:
        if name.text is not None:
            return name
        else:
            next_name = name.find(rf"{{{SRC_NS}}}name")     
            return _get_name_from_nested_name(next_name)

    return None

def _get_full_name_text_from_name(name):
    name_txt = ''

    if name is not None:
        if name.text is not None:
            name_txt = name.text
        else:
            for n_txt in name.itertext():
                name_txt += n_txt

    return name_txt

def _get_signature(element):
    def _join(values, delimiter=' '):
        return delimiter.join(i.strip() for i in values if i.strip())

    components = list()
    type_ = element.find('src:type', NS)
    if type_ is not None:
        components.append(_join(type_.itertext()))
        components.append(' ')

    components.append(_get_name(element))
    parameters = element.find('src:parameter_list', NS)
    if parameters:
        components.append('(')
        parameters = list(parameters.iterfind('src:parameter', NS))
        for index, parameter in enumerate(parameters):
            components.append(_join(parameter.itertext()))
            if index < len(parameters) - 1:
                components.append(', ')
        components.append(')')

    return ''.join(components) if components else None

def _get_paramter_count(element):
    parameters = element.find('src:parameter_list', NS)
    if (parameters):
        p = list(parameters.iterfind('src:parameter', NS))
        return len(parameters)

    return 0

def get_srcml(contents, language):
    process = subprocess.run(["srcml", '--position', '--text', contents, "--language", language], check=True, text=True, capture_output=True) 
    return process.stdout

def get_srcml_from_path(path, language):
    process = subprocess.run(["srcml", path, "--position", "--language", language],  check=True, text=True, capture_output=True) 
    return process.stdout

def _get_expr_signatures(element):
    elestr_list = []
    
    # print('-' * 30)
    # print("expr:")
    for child in element.iter():       
        index_str = ""
        ele_sub_str = ""

        if(re.search(rf"{{{SRC_NS}}}expr_stmt",str(child))):
            previous_call_name = ""

            #print (child)
            
            sub_str = ""
            for subel in child.iter():
                if re.search(rf"{{{SRC_NS}}}call", str(subel)):
                    previous_call_name = subel.find(rf"{{{SRC_NS}}}name")          
                    previous_call_name = previous_call_name.text if previous_call_name is not None else ""
                # if(re.search(rf"{{{SRC_NS}}}index", str(subel))):
                #     for indexEl in subel.iter():
                #         if(indexEl is not None and indexEl.text is not None):
                #             index_str+=indexEl.text

                
                    #print(index_str)
                    
                #Calls to other functions are already being counted for fan-out, so we dont need to include them here
                # if subel.text and subel.text != previous_call_name:
                #     ele_sub_str+= subel.text

            for subexpr in child.itertext():
                sub_str += subexpr
            
            sub_str = re.sub(r"\s", "", sub_str)
            if(re.search(r"\*{0,2}[a-zA-Z][a-zA-Z0-9]*(?<!\!)\=(?!\=)", sub_str) or re.search(r"[a-zA-Z][a-zA-Z0-9]*\-\>[a-zA-Z][a-zA-Z0-9]*(?<!\!)\=(?!\=)", sub_str)):
                elestr_list.append(sub_str)           
            
                #print("    " + sub_str)
            
        if(re.search(rf"{{{SRC_NS}}}decl_stmt", str(child))):
            decls = child.findall(rf"{{{SRC_NS}}}decl")

            #print(decls)
            decl_list=[]
            
            
            for decl in decls:
                decl_sub_str = ""
                decl_init = decl.find(rf"{{{SRC_NS}}}init")
                decl_init_txt = decl_init.text if decl_init is not None and decl_init.text is not None else ""

                decl_type = decl.find(rf"{{{SRC_NS}}}type")
                decl_mod = decl_type.find(rf"{{{SRC_NS}}}modifier") if decl_type is not None else None
                decl_mod_txt = decl_mod.text if decl_mod is not None and decl_mod.text is not None else ""

                if decl_init is not None and decl_mod_txt == "*":
                    for sub_expr in decl.itertext():
                        if(sub_expr is not None):
                            decl_sub_str += sub_expr
                            decl_sub_str += " "                                   


                    decl_sub_str = re.sub(r".*\*", "*", decl_sub_str)
                    decl_sub_str = re.sub(r"\s*", "", decl_sub_str)
                    decl_list.append(decl_sub_str)

                        
            if(decl_list != []):
                #print(decl_list)
                elestr_list = [*elestr_list, *decl_list]

        if(len(ele_sub_str)):
            elestr_list.append(ele_sub_str)

    # print("expr sigs: ")
    # print('♠'*20)
    # [print(decl) for decl in elestr_list]

    # print("elestr_list:") 
    # print(elestr_list)
    return elestr_list

def _get_decl_signatures(element):
    elestr_list = []

    for child in element.iter():
        if re.search(rf"{{{SRC_NS}}}decl_stmt", str(child)):
            decls = child.findall(rf"{{{SRC_NS}}}decl")

            for decl in decls:
                decl_type = decl.find(rf"{{{SRC_NS}}}type") if decl is not None else None

                decl_name_el = decl.find(rf"{{{SRC_NS}}}name") if decl is not None else None
                decl_name = decl_name_el

                if decl_name_el is not None and decl_name_el.text is None:
                    decl_name = next((el for el in decl_name_el.iter() if re.search(rf"{{{SRC_NS}}}name", str(el)) and el.text is not None), None)

                decl_name_txt = decl_name.text if decl_name is not None and decl_name.text is not None else ""

                type_specifier = decl_type.find(rf"{{{SRC_NS}}}specifier") if decl_type is not None else None
                type_specifier_txt = type_specifier.text if type_specifier is not None and type_specifier.text is not None else ""

                type_name = decl_type.find(rf"{{{SRC_NS}}}name") if decl_type is not None else None
                type_name_txt = type_name.text if type_name is not None and type_name.text is not None else ""
                
                index_tag = None
                index_str = ""

                if type_name_txt == "" and type_name is not None:
                    i_type_name = type_name.find(rf"{{{SRC_NS}}}name")
                    
                    type_name_txt = i_type_name.text if i_type_name is not None and i_type_name.text is not None else ""
                    #print("index name: " + str(type_name_txt))

                    type_name_index = type_name.find(rf"{{{SRC_NS}}}index")
                    index_tag = type_name_index                   

                    if type_name_index is not None:
                        for i_str in type_name_index.itertext():
                            index_str += i_str

                type_modifier = decl_type.find(rf"{{{SRC_NS}}}modifier") if decl_type is not None else None
                type_modifier_txt = type_modifier.text if type_modifier is not None and type_modifier.text is not None else ""

                decl_pos = decl.attrib[rf"{{{POS_NS}}}start"].split(':') if rf"{{{POS_NS}}}start" in decl.attrib.keys() else [-1, -1]
                decl_pos_row = int(decl_pos[0])

                if type_name != "":                    
                    elestr_list.append({
                        "specifier": type_specifier_txt,
                        "type": type_name_txt,
                        "modifier": type_modifier_txt,
                        "name": decl_name_txt,
                        "index_tag": index_tag,
                        "index_str": index_str,
                        "signature": re.sub("/s+", " ", " ".join([type_specifier_txt, type_name_txt, type_modifier_txt, decl_name_txt]).rstrip()),
                        "pos_row": decl_pos_row
                    })
         
    return elestr_list

def _get_param_data(function):
    parameter_list = function.find(rf"{{{SRC_NS}}}parameter_list")
    parameters = parameter_list.findall(rf"{{{SRC_NS}}}parameter")

    parameter_declarations = []
    parameters_passed_by_reference = []

    for param in parameters:
        decl = param.find(rf"{{{SRC_NS}}}decl")  
        decl_name = decl.find(rf"{{{SRC_NS}}}name") if decl is not None else None
        decl_name_txt = decl_name.text if decl_name is not None and decl_name.text else ""

        decl_type = decl.find(rf"{{{SRC_NS}}}type") if decl is not None else None
        decl_type_name = decl_type.find(rf"{{{SRC_NS}}}name") if decl_type is not None else None
        decl_type_name_txt = decl_type_name.text if decl_type_name is not None and decl_type_name.text else ""

        decl_type_modifier = decl_type.find(rf"{{{SRC_NS}}}modifier") if decl_type is not None else None  
        decl_type_modifier_txt = decl_type_modifier.text if decl_type_modifier is not None and decl_type_modifier.text else ""

        if(re.search(r"\*|\&", decl_type_modifier_txt)):
            parameters_passed_by_reference.append({"type": decl_type_name_txt, "modifier": decl_type_modifier_txt, "name": decl_name_txt})

        if(decl_name_txt != ""):
            parameter_declarations.append({"type": decl_type_name_txt, "modifier": decl_type_modifier_txt, "name": decl_name_txt})
        
    return {"parameters" : parameter_declarations, "parameters_passed_by_reference": parameters_passed_by_reference}
            
def _get_function_calls_from_macro_tags(function):
    macro_list = []
    macro_calls_list = []

    for child in function.iter():
        if(re.search(rf"{{{SRC_NS}}}macro", str(child))):
            macro_name = child.find(rf"{{{SRC_NS}}}name")
            macro_name_txt = macro_name.text if macro_name is not None and macro_name.text is not None else ""
            macro_arg_list = child.find(rf"{{{SRC_NS}}}argument_list")
            macro_args = macro_arg_list.findall(rf"{{{SRC_NS}}}argument") if macro_arg_list is not None else None

            child_macro_code_block = ""

            if(macro_args is not None):
                for arg in macro_args:
                    arg_text = arg.text if arg is not None and arg.text is not None else ""                    

                    if(arg_text != ""):
                        srcml = get_srcml(arg_text, language)
                        rootet = ET.fromstring(srcml)

                        if(re.search(r"{(.)+}", arg_text, flags=re.MULTILINE|re.DOTALL)):                           
                            for child in rootet.iter():        
                                call_name_txt = ""       
                                arg_list = []

                                if(re.search(rf"{{{SRC_NS}}}call", str(child))):
                                    call_name = child.find(rf"{{{SRC_NS}}}name")
                                    call_name_txt = call_name.text if call_name is not None and call_name.text is not None else ""

                                    if call_name_txt != "":
                                        macro_list.append(call_name_txt)

                                if(re.search(rf"{{{SRC_NS}}}argument_list", str(child))):
                                    for arg in child.iter(rf"{{{SRC_NS}}}argument"):
                                        arg_expr = arg.find(rf"{{{SRC_NS}}}expr")
                                        arg_expr_call = arg.find(rf"{{{SRC_NS}}}call") if arg_expr is not None else None
                                        arg_expr_call_name = arg_expr_call.find(rf"{{{SRC_NS}}}name") if arg_expr_call is not None else None
                                        arg_expr_call_name_txt = arg_expr_call_name.text if arg_expr_call is not None and arg_expr_call.text is not None else ""

                                        if (arg_expr_call_name_txt != ""):
                                            arg_list.append(arg_expr_call_name_txt)                                
                                
                                macro_list = [call for call in macro_list if call not in arg_list]                                

                                         
    return list(set(macro_list))

def _get_local_function_names(root):
    func_names = []
    for child in root.iter():
        if(re.search(rf"{{{SRC_NS}}}function", str(child))):
            func_name = child.find(rf"{{{SRC_NS}}}name")
            func_name_txt = func_name.text if func_name is not None and func_name.text is not None else ""
            
            if func_name_txt != "":
                func_names.append(func_name_txt)

    return list(set(func_names))

def _get_all_function_call_info(function):
    call_data = {}

    for child in function.iter():
        if(re.search(rf"{{{SRC_NS}}}call", str(child))):
            call_name = child.find(rf"{{{SRC_NS}}}name")
            call_name_txt = _get_full_name_text_from_name(call_name)


            if call_name_txt not in list(call_data) and call_name_txt != "":
                call_data[call_name_txt] ={
                    "cumulative_args": []
                }

            if(call_name_txt != ""):
                call_arg_list = child.find(rf"{{{SRC_NS}}}argument_list")
                call_args = call_arg_list.findall(rf"{{{SRC_NS}}}argument") if call_arg_list is not None else []

                for arg in call_args:
                    arg_expr = arg.find(rf"{{{SRC_NS}}}expr")
                    arg_expr_name = arg_expr.find(rf"{{{SRC_NS}}}name") if arg_expr is not None else None
                    arg_expr_name_txt = arg_expr_name.text if arg_expr_name is not None and arg_expr_name.text is not None else ""

                    if(arg_expr_name_txt != ""):
                        call_data[call_name_txt]["cumulative_args"] = [*call_data[call_name_txt]["cumulative_args"], arg_expr_name_txt]

    for key in list(call_data):
        call_data[key]["cumulative_args"] = list(set(call_data[key]["cumulative_args"]))

    return call_data

def _parse_function_call(element):
    call_data = {}

    if(re.search(rf"{{{SRC_NS}}}call", str(element))):
            call_name = element.find(rf"{{{SRC_NS}}}name")
            call_name_txt = _get_full_name_text_from_name(call_name)


            if call_name_txt not in list(call_data) and call_name_txt != "":
                call_data[call_name_txt] ={
                    "cumulative_args": []
                }

            if(call_name_txt != ""):
                call_arg_list = element.find(rf"{{{SRC_NS}}}argument_list")
                call_args = call_arg_list.findall(rf"{{{SRC_NS}}}argument") if call_arg_list is not None else []

                for arg in call_args:
                    arg_expr = arg.find(rf"{{{SRC_NS}}}expr")
                    arg_expr_name = arg_expr.find(rf"{{{SRC_NS}}}name") if arg_expr is not None else None
                    arg_expr_name_txt = arg_expr_name.text if arg_expr_name is not None and arg_expr_name.text is not None else ""

                    if(arg_expr_name_txt != ""):
                        call_data[call_name_txt]["cumulative_args"] = [*call_data[call_name_txt]["cumulative_args"], arg_expr_name_txt]

    for key in list(call_data):
        call_data[key]["cumulative_args"] = list(set(call_data[key]["cumulative_args"]))

    if call_data != {}:
        return call_data

    return None

def _parse_macro_call(element, language):
    macro_list = []
    macro_calls = {}
    if(re.search(rf"{{{SRC_NS}}}macro", element.tag)):
        macro_name = element.find(rf"{{{SRC_NS}}}name")
        macro_name_txt = macro_name.text if macro_name is not None and macro_name.text is not None else ""
        macro_arg_list = element.find(rf"{{{SRC_NS}}}argument_list")
        macro_args = macro_arg_list.findall(rf"{{{SRC_NS}}}argument") if macro_arg_list is not None else None

        child_macro_code_block = ""

        if(macro_args is not None):
            for arg in macro_args:
                arg_text = arg.text if arg is not None and arg.text is not None else ""                    

                if(arg_text != ""):
                    srcml = get_srcml(arg_text, language)
                    rootet = ET.fromstring(srcml)

                    if(re.search(r"{(.)+}", arg_text, flags=re.MULTILINE|re.DOTALL)):                           
                        for child in rootet.iter():        
                            call_name_txt = ""       
                            arg_list = []

                            call = _parse_function_call(child)

                            if call is not None:
                                macro_calls = {**macro_calls, **call}                         

    if macro_calls != {}:                               
        return macro_calls

    return None

def _parse_declaration(element, parent_struct_name, parent_struct_type, belongs_to_file):
    if re.search(rf"{{{SRC_NS}}}decl_stmt|control", element.tag):
        decls = []

        if re.search(rf"{{{SRC_NS}}}control", element.tag):
            control_init = element.find(rf"{{{SRC_NS}}}init")
            control_init_decls = control_init.findall(rf"{{{SRC_NS}}}decl")
            #print (control_init_decls)
            decls = [*decls, *control_init_decls]

        decls = [*decls, *element.findall(rf"{{{SRC_NS}}}decl")]

        for decl in decls:
            decl_type = decl.find(rf"{{{SRC_NS}}}type") if decl is not None else None

            decl_name_el = decl.find(rf"{{{SRC_NS}}}name") if decl is not None else None
            decl_name = decl_name_el

            if decl_name_el is not None and decl_name_el.text is None:
                decl_name = next((el for el in decl_name_el.iter() if re.search(rf"{{{SRC_NS}}}name", str(el)) and el.text is not None), None)

            decl_name_txt = decl_name.text if decl_name is not None and decl_name.text is not None else ""

            type_specifier = decl_type.find(rf"{{{SRC_NS}}}specifier") if decl_type is not None else None
            type_specifier_txt = type_specifier.text if type_specifier is not None and type_specifier.text is not None else ""

            type_name = decl_type.find(rf"{{{SRC_NS}}}name") if decl_type is not None else None
            type_name_txt = type_name.text if type_name is not None and type_name.text is not None else ""
            
            index_tag = None
            index_str = ""

            if type_name_txt == "" and type_name is not None:
                i_type_name = type_name.find(rf"{{{SRC_NS}}}name")
                
                type_name_txt = i_type_name.text if i_type_name is not None and i_type_name.text is not None else ""
                #print("index name: " + str(type_name_txt))

                type_name_index = type_name.find(rf"{{{SRC_NS}}}index")
                index_tag = type_name_index                   

                if type_name_index is not None:
                    for i_str in type_name_index.itertext():
                        index_str += i_str

            type_modifier = decl_type.find(rf"{{{SRC_NS}}}modifier") if decl_type is not None else None
            type_modifier_txt = type_modifier.text if type_modifier is not None and type_modifier.text is not None else ""

            decl_pos = decl.attrib[rf"{{{POS_NS}}}start"].split(':') if rf"{{{POS_NS}}}start" in decl.attrib.keys() else [-1, -1]
            decl_pos_row = int(decl_pos[0])


            if type_name != "":                    
                return {
                    "specifier": type_specifier_txt,
                    "type": type_name_txt,
                    "modifier": type_modifier_txt,
                    "name": decl_name_txt,
                    "index_tag": index_tag,
                    "index_str": index_str,
                    "signature": re.sub("/s+", " ", " ".join([type_specifier_txt, type_name_txt, type_modifier_txt, decl_name_txt]).rstrip()),
                    "pos_row": decl_pos_row,
                    "file_name": belongs_to_file,                    
                    "parent_structure_name": parent_struct_name,
                    "parent_structure_type": parent_struct_type,
                }

        
    return None
        
#Do not count calls that are passed in as a parameters to another call
#Not picking up all calls in a function!

def _get_exprs_from_function(function):
    expr_list = []

    for child in function.iter():
        if re.search(rf"{{{SRC_NS}}}expr", str(child)):
            expr_list.append(child)

    return expr_list

def _get_unique_calls_from_function(function):
    #Calls should be unique
    call_names = []
    cumulative_argument_list_calls = []
    sig = _get_signature(function)

    for child in function.iter():
        if(re.search(r"git_tree_entry_bypath", sig)):
           #print(child)
            pass

        if(re.search(rf"call", str(child))):
            name = child.find(rf"{{{SRC_NS}}}name")


            #if(child.text is not None):
            
            #print(child.text)

            arg_list = child.find(rf"{{{SRC_NS}}}argument_list")

            if(arg_list is not None):
                args = arg_list.findall(rf"{{{SRC_NS}}}argument")

                for arg in args:
                    expr = arg.find(rf"{{{SRC_NS}}}expr")
                    expr_call = expr.find(rf"{{{SRC_NS}}}call") if expr is not None else None

                    name = expr_call.find(rf"{{{SRC_NS}}}name") if expr_call is not None else None
                    name_txt = name.text if name is not None and name.text is not None else ""

                    if name_txt != "":
                        cumulative_argument_list_calls.append(name_txt)
                        #print(name_txt)

            name = child.find(rf"{{{SRC_NS}}}name")
            
            if name is not None:
                call_names.append(_get_full_name_text_from_name(name))    


    #print(call_names)
    #call_names = list(set(call_names))
    #print(call_names) call not in cumulative_argument_list_calls and 
    #new_call_names = list( filter(lambda call: call not in cumulative_argument_list_calls and call is not None and call not in C_LIB_FUNCTIONS, list(set(call_names))))
    new_call_names = [call for call in list(set(call_names)) if call.rstrip() not in cumulative_argument_list_calls and call is not None and call.rstrip() not in C_LIB_FUNCTIONS]
    #[print(call) for call in new_call_names]

    return new_call_names

def _get_pointer_declarations_from_expr(function):
    pointer_declarations = []

    for child in function.iter():
        if(re.search(rf"{{{SRC_NS}}}decl_stmt", str(child))):
            decls = child.findall(rf"{{{SRC_NS}}}decl")
            for decl in decls:
                decl_name = decl.find(rf"{{{SRC_NS}}}name")
                decl_name_txt = decl_name.text if decl_name is not None and decl_name.text is not None else ""

                decl_type = decl.find(rf"{{{SRC_NS}}}type")   
                decl_type_name = decl_type.find(rf"{{{SRC_NS}}}name")
                decl_type_specifier = decl_type.find(rf"{{{SRC_NS}}}specifier")
                
                decl_type_specifier_txt = decl_type_specifier.text if decl_type_specifier is not None and decl_type_specifier.text is not None else ""
                decl_type_name_txt = decl_type_name.text if decl_type_name is not None and decl_type_name.text is not None else ""

                decl_type_modifier = decl_type.find(rf"{{{SRC_NS}}}modifier")   
                decl_type_modifier_txt = decl_type_modifier.text if decl_type_modifier is not None and decl_type_modifier.text else ""

                decl_pos = decl.attrib[rf"{{{POS_NS}}}start"].split(':') if rf"{{{POS_NS}}}start" in decl.attrib.keys() else [-1, -1]
                decl_pos_row = int(decl_pos[0])

                if(decl_type_modifier_txt == "*"): #and decl_type_specifier_txt != "const"):
                    pointer_declarations.append({"type": decl_type_name_txt, "modifier": decl_type_modifier_txt, "name": decl_name_txt, "pos_row": decl_pos_row})

    # print("pointer decls: ")
    # print('♠'*20)
    # [print(decl) for decl in pointer_declarations]

    #print(pointer_declarations)
    return pointer_declarations

def _get_enum_declarations(root):
    enum_names = []

    for el in root.iter():
        if re.search(rf"{{{SRC_NS}}}enum", str(el)):
           
            enum_block = el.find(rf"{{{SRC_NS}}}block")
            enum_decls = enum_block.findall(rf"{{{SRC_NS}}}decl") if enum_block is not None else []

            for decl in enum_decls:
                decl_name = decl.find(rf"{{{SRC_NS}}}name")
                if decl_name is not None and decl_name.text is not None:
                    enum_names.append(decl_name)

    return list(set(enum_names))

def _calculate_unique_path_count(function):
    paths = 1

    for child in function.iter():
        #print(child)
        sub_path = 1
        
        if re.search(rf'{{{SRC_NS}}}(if_stmt|else|then|case|default)', child.tag): #or re.search(rf'{{{SRC_CPP}}}(if|ifdef)', child.tag):
            if re.search(rf'{{{SRC_NS}}}(if_stmt|else)', child.tag):
                if_else_exprs= [*child.findall(rf'{{{SRC_NS}}}if')] #, *child.findall(rf'{{{SRC_NS}}}else')]
                op_count = 0

                for if_child in if_else_exprs:
                    if_cond = if_child.find(rf'{{{SRC_NS}}}condition')
                    if_cond_expr = if_cond.find(rf'{{{SRC_NS}}}expr') if if_cond is not None else None
                    if_cond_ops = if_cond_expr.findall(rf'{{{SRC_NS}}}operator') if if_cond_expr is not None else []

                    for op in if_cond_ops:
                        if op is not None and op.text is not None:
                            if op.text == '&&' or op.text == '||':
                                op_count += 1


                    for if_child_el in if_child.iter():
                        if re.search(rf'{{{SRC_NS}}}(if_stmt|else)', if_child_el.tag): #or re.search(rf'{{{SRC_CPP}}}(if)', if_child_el.tag):
                            sub_path *= (2 + op_count)
                

            if sub_path > 1:
                paths += sub_path
            else:
                paths+=1


    return paths

def _get_fan_out_from_expr_global_var_write(expr, function_declaration_list, parameters_passed_by_reference, pointer_declarations, calls, variable_writes, parent_declarations):
    fan_out = 0

    decl_names = [d["name"] for d in [*function_declaration_list]] 

    pointer_names = [p["name"] for p in [*parameters_passed_by_reference, *pointer_declarations]]

    expr_str = ""

    expr_children = [child for child in expr.iter()]     
    expr_str = ''.join([child for child in expr.itertext()])  

    expr_row_pos = int(expr.attrib[rf"{{{POS_NS}}}start"].split(':')[0]) if rf"{{{POS_NS}}}" in expr.attrib.keys() else -1

    expr_names = expr.findall(rf"{{{SRC_NS}}}name")
    operators = expr.findall(rf"{{{SRC_NS}}}operator")

    incr_decr_op = next((op for op in operators if op is not None and op.text is not None and re.fullmatch(r"^\+\+|\-\-$", op.text)), None)
    incr_decr_op_txt = incr_decr_op.text if incr_decr_op is not None and incr_decr_op.text is not None else ''
    
    incr_decr_op_pos = incr_decr_op.attrib[rf"{{{POS_NS}}}start"].split(':') if incr_decr_op is not None and rf"{{{POS_NS}}}start" in incr_decr_op.attrib.keys() else [-1, -1]
    incr_decr_op_row = int(incr_decr_op_pos[0])
    incr_decr_op_col = int(incr_decr_op_pos[1])

    equals_ops = [op for op in operators if op is not None and op.text is not None and re.fullmatch(r"^\=|\+\=|\-\=|\*\=|\\\=$", op.text)]

    if len(equals_ops) == 0:
        equals_ops = [None]

    last_equals_op_txt = equals_ops[-1].text if equals_ops[-1] is not None and equals_ops[-1].text is not None else ''

    last_equals_op_pos = equals_ops[-1].attrib[rf"{{{POS_NS}}}start"].split(':') if equals_ops[-1] is not None and rf"{{{POS_NS}}}start" in equals_ops[-1].attrib.keys() else [-1, -1]
    last_equals_op_row = int(last_equals_op_pos[0])
    last_equals_op_col = int(last_equals_op_pos[1])

    first_equals_op_txt = equals_ops[0].text if equals_ops[0] is not None and equals_ops[0].text is not None else ''

    first_equals_op_pos = equals_ops[0].attrib[rf"{{{POS_NS}}}start"].split(':') if equals_ops[0] is not None and rf"{{{POS_NS}}}start" in equals_ops[0].attrib.keys() else [-1, -1]
    first_equals_op_row = int(first_equals_op_pos[0])
    first_equals_op_col = int(first_equals_op_pos[1])

    fan_out_var_candidates = []

    if last_equals_op_txt != '' or incr_decr_op_txt != '':
        # print(expr_str)
        if len(expr_names) > 0:
            first_expr_name = expr_names[0]
            first_expr_name_txt = ''
            first_expr_name_txt_full = ''            
            
            
            for name in expr_names:
                    name_pos = name.attrib[rf"{{{POS_NS}}}start"].split(':') 
                    name_pos_row = int(name_pos[0])  
                    name_pos_col = int(name_pos[1])  

                    expr_sub_names = name.findall(rf"{{{SRC_NS}}}name")                          
                    expr_sub_name = _get_name_from_nested_name(expr_sub_names[0]) if len(expr_sub_names) > 1 else name 
                    expr_sub_name_pos = expr_sub_name.attrib[rf"{{{POS_NS}}}start"].split(':') if expr_sub_name is not None and rf"{{{POS_NS}}}start" in expr_sub_name.attrib.keys() else [-1, -1]
                    expr_sub_name_pos_row = int(expr_sub_name_pos[0])
                    expr_sub_name_pos_col = int(expr_sub_name_pos[1])
                    
                    expr_index = name.find(rf"{{{SRC_NS}}}index")  
                    expr_index_txt = ''.join(child_txt for child_txt in expr_index.text if expr_index.text is not None) if expr_index is not None else ''                       

                    expr_index_pos = expr_index.attrib[rf"{{{POS_NS}}}start"].split(':') if expr_index is not None and rf"{{{POS_NS}}}start" in expr_index.keys() else [-1, -1]
                    expr_index_pos_row = int(expr_index_pos[0])
                    expr_index_pos_col = int(expr_index_pos[1])

                    first_expr_name_txt = expr_sub_name.text if expr_sub_name is not None and expr_sub_name.text is not None else ''.join([child_txt for child_txt in first_expr_name.itertext()])
                    name_signature = ''.join([child_txt for child_txt in name.itertext()])
                    
                    name_op = name.findall(rf"{{{SRC_NS}}}operator")
                    member_access_op = next((op for op in name_op if op is not None and op.text is not None and (op.text == '->' or op.text == '.')), None)
                    member_access_op_pos = member_access_op.attrib[rf"{{{POS_NS}}}start"].split(':') if member_access_op is not None and rf"{{{POS_NS}}}start" in member_access_op.attrib.keys() else [-1, -1]
                    member_access_op_pos_row = int(member_access_op_pos[0])
                    member_access_op_pos_col = int(member_access_op_pos[1])

                    members_accessed = []
                    expr_mod_statements = []

                    index_accessed_str = ''

                    if (member_access_op is not None
                        and member_access_op_pos_row == expr_sub_name_pos_row 
                        and member_access_op_pos_col > expr_sub_name_pos_col 
                        and (member_access_op_pos_col < first_equals_op_col or incr_decr_op_col != -1)
                        ):                        

                        member_accessed_str = ''

                        #for child in expr_sub_names:
                        for child in expr_children:
                            child_pos = child.attrib[rf"{{{POS_NS}}}start"].split(':') if rf"{{{POS_NS}}}start" in child.attrib.keys() else [-1, -1]
                            child_pos_row = int(child_pos[0])
                            child_pos_col = int(child_pos[1])

                            child_txt = ''.join(child.itertext()) if child.text is None else child.text

                            if child_pos_row == member_access_op_pos_row and child_pos_col > member_access_op_pos_col and (child_pos_col < first_equals_op_col or incr_decr_op_col != -1):
                                
                                if child_txt != '':       
                                    if expr_index_pos_col > member_access_op_pos_col and expr_index_pos_row == member_access_op_pos_row:
                                        index_accessed_str += child_txt
                                    else:            
                                        member_accessed_str += child_txt
                            elif child_pos_col < first_equals_op_col and expr_index_pos_col < first_equals_op_col and expr_index_pos_col != -1:
                                if child_txt != '':      
                                    if expr_index_pos_row == member_access_op_pos_row:
                                        index_accessed_str += child_txt
                                
                        if member_accessed_str != '':
                            members_accessed.append(member_accessed_str)

                    elif member_access_op is None and expr_index is None: 
                        expr_mod_statements.append(expr_str)

                    # Checks to see if a variable that is in declarations was invoked before it was declared and therefore still a valid candidate in 
                    # being counted towards the fan-out metric
                    invoked_before_declared = False if next((decl for decl in function_declaration_list if first_expr_name_txt == decl["name"] and decl["pos_row"] > expr_row_pos), None) is not None else True
                    if first_expr_name_txt != "this" and (first_expr_name_txt in pointer_names or first_expr_name_txt not in decl_names or invoked_before_declared):                          
                        fan_out_var_candidates.append({
                        "name": first_expr_name_txt,
                        "signature": name_signature,
                        "row_pos": name_pos_row,
                        "col_pos": name_pos_col,
                        "members_accessed": members_accessed,
                        "indices" : [index_accessed_str],
                        "expr_mod_statements": expr_mod_statements
                        })  

        for cand in fan_out_var_candidates:
            if last_equals_op_txt != '' and last_equals_op_col > cand["col_pos"] and last_equals_op_row == cand["row_pos"]:
                if cand["name"] not in variable_writes.keys():
                    variable_writes[cand["name"]] = {
                        'expressions': cand["expr_mod_statements"],
                        'members_modified': cand["members_accessed"],
                        'indices_modified': cand["indices"]
                    }
                else:
                    variable_writes[cand["name"]]['expressions'] = [*variable_writes[cand["name"]]['expressions'], *cand["expr_mod_statements"]]
                    variable_writes[cand["name"]]['members_modified'] = [*variable_writes[cand["name"]]['members_modified'], *cand["members_accessed"]]
                    variable_writes[cand["name"]]['indices_modified'] = [*variable_writes[cand["name"]]['indices_modified'], *cand["indices"]]
            elif incr_decr_op_txt and incr_decr_op_row == cand["row_pos"]:
                if cand["name"] not in variable_writes.keys():
                    variable_writes[cand["name"]] = {
                        'expressions': cand["expr_mod_statements"],
                        'members_modified': cand["members_accessed"],
                        'indices_modified': cand["indices"]
                    }
                else:
                    variable_writes[cand["name"]]['expressions'] = [*variable_writes[cand["name"]]['expressions'], *cand["expr_mod_statements"]]
                    variable_writes[cand["name"]]['members_modified'] = [*variable_writes[cand["name"]]['members_modified'], *cand["members_accessed"]]
                    variable_writes[cand["name"]]['indices_modified'] = [*variable_writes[cand["name"]]['indices_modified'], *cand["indices"]]
    
def _count_fan_out(variable_writes):
    fan_out = 0

    print_data = False
    for key in list(variable_writes):        
        if len(variable_writes[key]['expressions']) > 0:
            fan_out += 1

        members_modded = list(set([m for m in variable_writes[key]['members_modified'] if m.rstrip() != '']))
        indicies_modded = list(set([i for i in variable_writes[key]['indices_modified'] if i.rstrip() != '']))

        fan_out += len(members_modded) + len(indicies_modded)

        if print_data:
            print("variable: " + key)
            print("expressions: ")
            for expr in variable_writes[key]['expressions']:
                print("    " + expr)


            print("\nmodified members:")
            for mem in members_modded:
                print('    ' + mem)

            print("\nmodified indices:")
            for indx in indicies_modded:
                print('   ' + indx)       

    return fan_out

def _get_fan_in_from_expr_global_var_read(expr, calls, function_declarations, pointer_declarations, params, local_function_names, enums, read_variable_names, function_throws_exception_names, parent_declarations):
    fan_in = 0
    none_ptr_declaration_var_names = [d["name"] for d in function_declarations]
    pointer_declaration_var_names = [d["name"] for d in pointer_declarations]
    parent_declaration_var_names= [d["name"] for d in parent_declarations]

    #print(local_function_names)
    pointer_parameter_names = [p["name"] for p in params if re.fullmatch(r"^\*|ref|\&$", p["modifier"])]

    expr_names = expr.findall(rf"{{{SRC_NS}}}name")

    expr_pos = expr.attrib[rf"{{{POS_NS}}}start"].split(':') if expr is not None and rf"{{{POS_NS}}}start" in expr.attrib.keys() else [-1, -1]
    expr_pos_row = int(expr_pos[0])
    expr_pos_col = int(expr_pos[1])

    ops = expr.findall(rf"{{{SRC_NS}}}operator") if expr is not None else None
    last_op = next((op for op in list(reversed(ops)) if op is not None and op.text is not None and re.fullmatch(r"^\=|\+\=|\-\=|\*\=|\\\=$", op.text)), None)

    incr_decr_op = next((op for op in ops if op is not None and op.text is not None and re.fullmatch(r"^\+\+|\-\-$", op.text)), None)
    incr_decr_op_txt = incr_decr_op.text if incr_decr_op is not None and incr_decr_op.text is not None else ''
    
    incr_decr_op_pos = incr_decr_op.attrib[rf"{{{POS_NS}}}start"].split(':') if incr_decr_op is not None and rf"{{{POS_NS}}}start" in incr_decr_op.attrib.keys() else [-1, -1]
    incr_decr_op_row = int(incr_decr_op_pos[0])
    incr_decr_op_col = int(incr_decr_op_pos[1])

    op_txt = last_op.text if last_op is not None and last_op.text is not None else ''

    equal_op_pos = last_op.attrib[rf'{{{POS_NS}}}start'].split(':') if last_op is not None and rf'{{{POS_NS}}}start' in last_op.attrib.keys() else [-1, -1]
    equal_op_pos_row = int(equal_op_pos[0])
    equal_op_pos_col = int(equal_op_pos[1])

    for name in expr_names:        
        name_op = name.find(rf"{{{SRC_NS}}}operator")
        name_op_text = name_op.text if name_op is not None and name_op.text is not None else ""

        name_txt = _get_full_name_text_from_name(name)

        name_member_access_txt = re.split(r"\-\>|\[|\.", name_txt, 1)[0]

        name_pos = name.attrib[rf'{{{POS_NS}}}start'].split(':') if rf'{{{POS_NS}}}start' in name.attrib.keys() else [-1, -1]
        name_pos_row = int(name_pos[0])
        name_pos_col = int(name_pos[1])         

        if(
            name_pos_col >= equal_op_pos_col and 
            equal_op_pos_col <= incr_decr_op_col and 
            name_member_access_txt != "" and
            name_member_access_txt is not None and
            name_member_access_txt not in C_RESERVED_KEYWORDS and 
            name_member_access_txt not in C_LIB_STREAMS and 
            not re.match(r"^null$", name_member_access_txt, flags=re.IGNORECASE) and
        (
            (

                (
                    name_member_access_txt not in list(calls) and 
                    name_member_access_txt not in none_ptr_declaration_var_names and
                    
                    name_member_access_txt not in C_LIB_FUNCTIONS and        
                    name_member_access_txt not in local_function_names
                ) 
        or
            name_member_access_txt in parent_declaration_var_names and
            name_member_access_txt not in none_ptr_declaration_var_names
        ) 
        or 
            (
                name_member_access_txt == next((param["name"] for param in params if param["modifier"] == "*" or param["modifier"] == "&"), None)) and
                name_member_access_txt not in enums and
                name_member_access_txt not in function_throws_exception_names                
            )
        ):
            read_variable_names.append(name_txt)
            #print("     " + name_txt)

    read_variable_names = list(set([*read_variable_names])) 
    
def _count_fan_in(variable_reads):
    return len(variable_reads)

def _get_path_from_statement(statement):
    paths = 0
    sub_path = 1
        
    if re.search(rf'{{{SRC_NS}}}(if_stmt|else|then|case|default)', statement.tag): #or re.search(rf'{{{SRC_CPP}}}(if|ifdef)', child.tag):
        if re.search(rf'{{{SRC_NS}}}(if_stmt|else)', statement.tag):
            if_else_exprs= [*statement.findall(rf'{{{SRC_NS}}}if')] #, *child.findall(rf'{{{SRC_NS}}}else')]
            op_count = 0

            for if_child in if_else_exprs:
                if_cond = if_child.find(rf'{{{SRC_NS}}}condition')
                if_cond_expr = if_cond.find(rf'{{{SRC_NS}}}expr') if if_cond is not None else None
                if_cond_ops = if_cond_expr.findall(rf'{{{SRC_NS}}}operator') if if_cond_expr is not None else []

                for op in if_cond_ops:
                    if op is not None and op.text is not None:
                        if op.text == '&&' or op.text == '||':
                            op_count += 1


                for if_child_el in if_child.iter():
                    if re.search(rf'{{{SRC_NS}}}(if_stmt|else)', if_child_el.tag): #or re.search(rf'{{{SRC_CPP}}}(if)', if_child_el.tag):
                        sub_path *= (2 + op_count)
            

        if sub_path > 1:
            paths += sub_path
        else:
            paths+=1

    return paths

def _get_throws_expression_names(statement):
    exception_names = []

    if re.search(rf"{{{SRC_NS}}}throws", statement.tag):
        args = statement.findall(rf"{{{SRC_NS}}}argument")
        for arg in args:
            expr = arg.find(rf"{{{SRC_NS}}}expr")
            expr_name = expr.find(rf"{{{SRC_NS}}}name") if expr is not None else None

            name_txt = _get_full_name_text_from_name(expr_name)

            if name_txt != '':
                exception_names.append(name_txt)

    return exception_names

def _parse_function_for_metrics(root, function_dict, all_local_call_names, parent_struct_name, parent_struct_type, parent_declarations, file_name, enums, local_function_names, language):
    child = root

    if re.search(rf"{{{SRC_NS}}}function|constructor", child.tag): #or re.search(rf"{{{SRC_NS}}}constructor", child.tag):
        func_sig = parent_struct_name + " " + _get_signature(child)
        func_name = _get_name(child)
        #print('-------------------------------------------------------------------------------')
        print("    " + func_sig)
        #Do not analyze function prototypes. Only perform analysis on functions that have blocks of code in them
        block = child.find(rf"{{{SRC_NS}}}block")

        has_return_value = False

        init_fan_out = 0
        init_fan_in = 0

        if re.search(rf"{{{SRC_NS}}}constructor", child.tag):
            init_fan_out = 1
            init_fan_in = 1
        
        init_n_path = 1 

        throws_exception_names = []
        declarations = []
        pointer_decls = []
        
        calls = {}
        macro_calls = {}

        global_variable_writes = {}
        global_variable_reads = []

        if(block is not None):
            param_data = _get_param_data(child)
            param_count = len(param_data["parameters"])

            for func_child in child.iter():
                decl = _parse_declaration(func_child, parent_struct_name=parent_struct_name, parent_struct_type=parent_struct_type, belongs_to_file=file_name)
                call = _parse_function_call(func_child)
                macros = _parse_macro_call(func_child, language)
                throws = _get_throws_expression_names(func_child)

                if throws != []:
                    throws_exception_names = [*throws_exception_names, *throws]

                if decl is not None:
                    if decl["modifier"] == "*":
                        pointer_decls.append(decl)
                    else:
                        declarations.append(decl)

                if call is not None:
                    calls = {**calls, **call}
                    all_local_call_names = [*all_local_call_names, *call.keys()]
                
                if macros is not None:
                    macro_calls = {**macro_calls, **macros}

                init_n_path += _get_path_from_statement(func_child)

                if re.search(rf'{{{SRC_NS}}}return', func_child.tag) and has_return_value == False:  
                    return_expr = func_child.find(rf"{{{SRC_NS}}}expr")
                    if return_expr is not None:
                        init_fan_out += 1
                        has_return_value = True

                if re.search(rf"{{{SRC_NS}}}expr", func_child.tag):
                    _get_fan_out_from_expr_global_var_write(
                        expr = func_child, 
                        function_declaration_list = declarations,
                        parameters_passed_by_reference = param_data["parameters_passed_by_reference"], 
                        pointer_declarations = pointer_decls, 
                        calls = calls,
                        variable_writes = global_variable_writes,
                        parent_declarations = parent_declarations
                    )

                    _get_fan_in_from_expr_global_var_read(
                        expr = func_child, 
                        calls = calls, 
                        function_declarations = declarations,
                        pointer_declarations = pointer_decls,
                        params = param_data["parameters"],
                        local_function_names = local_function_names,
                        enums = enums,
                        read_variable_names = global_variable_reads,
                        function_throws_exception_names = throws_exception_names,
                        parent_declarations = parent_declarations
                        )

                    declaration_names = [d["name"] for d in declarations]

            global_variable_reads = list(set(global_variable_reads))
            if re.search(r"MoveSokoban", func_sig):
                print("decls: ")
                [print("    " + decl["name"]) for decl in declarations]
                print("params: ")
                [print("    " + str(p["name"])) for p in param_data["parameters_passed_by_reference"]]  
                print("Global var reads: ")
                [print("    " + str(r)) for r in global_variable_reads]


                print("Global variable writes: ")
                for key in global_variable_writes.keys():

                    print ("    " + key)

                    print ("     expressions:")
                    [print ("        " + e) for e in global_variable_writes[key]['expressions']]

                    print ("     members:")
                    [print ("        " + m) for m in global_variable_writes[key]['members_modified']]

                    print ("     indicies:")
                    [print ("        " + i) for i in global_variable_writes[key]['indices_modified']]



            init_fan_in += _count_fan_in(global_variable_reads)
            init_fan_out += _count_fan_out(global_variable_writes)

            non_local_function_calls = list(filter(lambda call: call not in declaration_names, list(set([*list(calls), *list(macro_calls)]))))


            #Add function to dict if not already in there
            #add_func_to_dict = next((False for key in function_dict.keys() if func_sig == key and parent_struct_name == function_dict[key]["parent_structure_name"] and parent_struct_type == function_dict[key]["parent_structure_type"]), True)

            if func_sig not in function_dict.keys():
                local_function_names.append(func_name)
                function_dict[func_sig] = {
                    "function_name": func_name,
                    "param_count": param_count,
                    "is_void": True,
                    "calls": calls,
                    "functions_called_by": [],
                    "fan_in": init_fan_in + param_count,
                    "fan_out": init_fan_out + len(non_local_function_calls),
                    "paths": init_n_path,
                    "has_return": has_return_value,
                    "return_counted": False,
                    "parent_structure_name": parent_struct_name,
                    "parent_structure_type": parent_struct_type,
                    "file_name": file_name
                }

    return function_dict

def _parse_metrics_for_structure(root, all_local_call_names, parent_struct_name, parent_struct_type, parent_declarations, file_name, local_function_names, enums, language):
    #print (list(root))

    parent_name_txt = parent_struct_name
    local_declarations = parent_declarations

    function_dict = {}
    for child in list(root):
        if re.search(rf"{{{SRC_NS}}}class|struct|namespace", child.tag):
            structure_code_blocks = child.findall(rf"{{{SRC_NS}}}block")

            parent_name = child.find(rf"{{{SRC_NS}}}name")
            new_parent_struct_type = re.sub(r"{.+}", "", child.tag)
            new_parent_name_txt = parent_struct_name + _get_full_name_text_from_name(parent_name)

            class_declarations = [_parse_declaration(element = decl, parent_struct_name = new_parent_name_txt, parent_struct_type = new_parent_struct_type, belongs_to_file = file_name) for decl in child.findall(rf"{{{SRC_NS}}}decl_stmt")]
            local_declarations = [*parent_declarations, *class_declarations]

            # for block in structure_code_blocks:
            function_dict = {**function_dict, 
            **_parse_metrics_for_structure(
            root = child, 
            all_local_call_names = all_local_call_names, 
            parent_struct_name = new_parent_name_txt, 
            parent_struct_type = new_parent_struct_type, 
            parent_declarations = local_declarations,
            file_name = file_name,
            local_function_names=local_function_names,
            enums = enums,
            language = language)}

        if re.search(rf"{{{SRC_NS}}}block", child.tag):
            function_dict = {**function_dict, 
            **_parse_metrics_for_structure(
            root = child, 
            all_local_call_names = all_local_call_names, 
            parent_struct_name = parent_name_txt, 
            parent_struct_type = parent_struct_type, 
            parent_declarations = local_declarations,
            file_name = file_name,
            local_function_names=local_function_names,
            enums = enums,
            language = language)}
        
        if re.search(rf"{{{SRC_NS}}}function|constructor", child.tag):
            #print(child)
            updated_function_dict = _parse_function_for_metrics(
                root = child, 
                function_dict = function_dict, 
                all_local_call_names = all_local_call_names, 
                parent_struct_name = parent_name_txt, 
                parent_struct_type = parent_struct_type, 
                parent_declarations = parent_declarations, 
                file_name = file_name,
                local_function_names=local_function_names,
                enums = enums,
                language = language)      

            function_dict = {**function_dict, **updated_function_dict}

    return function_dict

def _calculate_metrics(rootet, language, local_function_names, enums, file_name):
    #function_dict = {}
    all_local_call_names = []
    #classinator(rootet)

    parent_declarations = [_parse_declaration(element = decl, parent_struct_name = "file", parent_struct_type = "", belongs_to_file = file_name) for decl in rootet.findall(rf"{{{SRC_NS}}}decl_stmt")]

    function_dict = _parse_metrics_for_structure(
        root = rootet, 
        all_local_call_names = all_local_call_names,
        parent_struct_name = file_name,
        parent_struct_type = "",
        parent_declarations = parent_declarations,
        file_name = file_name,
        local_function_names=[],
        enums = enums,
        language = language
        )

    print_data = False

    for key in list(function_dict):
        locally_called_by = list(set([c for c in all_local_call_names if re.search(rf"{c}", function_dict[key]["function_name"])]))

        function_dict[key]["fan_in"] += len(locally_called_by)
        name = function_dict[key]["function_name"]
        file_name = function_dict[key]["file_name"]
        func_parent_name = function_dict[key]["parent_structure_name"]
        func_parent_type = function_dict[key]["parent_structure_type"]
        fan_in = function_dict[key]["fan_in"]
        fan_out = function_dict[key]["fan_out"]
        functions_called_by = function_dict[key]["functions_called_by"]
        paths = function_dict[key]["paths"]
        flow = (fan_in * fan_out)**2
        calls = function_dict[key]["calls"]

        if print_data:
            print ('─'*50)
            print ("    File Name: " + file_name)
            print ("  Parent Name: " + func_parent_name)
            print ("  Parent Type: " + func_parent_type)
            print ("     Func Sig: " + key)
            print ("    Func Name: " + name)
            print ("       Fan-in: " + str(fan_in))
            print ("      Fan-out: " + str(fan_out))
            print ("        Paths: " + str(paths))
            print ("         Flow: " + str(flow))
            print ("    Called by: ")
            [print("      " + call) for call in locally_called_by]
            print ("     Calls to: ")
            [print("      " + call) for call in calls.keys()]

    return function_dict

def _calculate_metrics_for_project(root, scitools_csv_path):
    metric_csv_list_headers = ['Name', 'File', 'CountOutput', 'CountPath', 'CountInput']
    csv_file_name = scitools_csv_path.split('.')[0]
    our_metric_data = []
    

    def normalize_function_name(name):
        split_func_name = name.split('.')
        name = split_func_name[-1] 

        #print("        func name: " + str(row))
        #print(split_func_name)

        return name

    #     row[1] = split_func_name[-2:] if len(split_func_name) >= 2 else row[1]
    # scitools_data_list = list(csv.reader(scitools_csv_file))
    # scitools_data_headers = scitools_data_list.pop(0)

    # for row in scitools_data_list:
    #     split_func_name = row[1].split('.')
    #     row[1] = split_func_name[-2:] if len(split_func_name) >= 2 else row[1]

    scitools_csv_file = open(scitools_csv_path)

    scitools_df = pd.read_csv(scitools_csv_file)


    scitools_csv_file.close()

    scitools_df["Name"] = scitools_df["Name"].apply(normalize_function_name)

    for i in scitools_df.values:
        print("func name: " + str(i[1]))
    
    for subdir, dirs, files in os.walk(root):
        for file in files:
            print(file)
            path = os.path.join(subdir, file)

            file_extension = file.split('.')[-1]
            language = "C"

            languages_from_extension = {
                'c': 'C',
                'cs': 'C#',
                'cpp': 'C++',
                'hpp': 'C++',
                'h': 'C++',
                'java': 'Java',
                'py': 'Python'
            }

            if file_extension in languages_from_extension.keys(): 
                language = languages_from_extension[file_extension] 
                srcml = get_srcml_from_path(path, language)
                root = ET.fromstring(srcml)

                local_function_names = _get_local_function_names(root)
                enums = _get_enum_declarations(root)

                function_dict = _calculate_metrics(rootet = root, language = language, local_function_names = local_function_names, enums = enums, file_name = file)

                for key in function_dict.keys():
                    function_name = function_dict[key]['function_name'] if language == "C" else function_dict[key]['parent_structure_name'] + '.' + function_dict[key]['function_name'] 
                    file_name = function_dict[key]['file_name']
                    fan_out = function_dict[key]['fan_out']
                    paths = function_dict[key]['paths']
                    fan_in = function_dict[key]['fan_in']

                    our_metric_data.append([function_name, file_name, fan_out, paths, fan_in])

    our_metric_df = pd.DataFrame(data=our_metric_data, columns=metric_csv_list_headers)
    our_metric_df["Name"] = our_metric_df["Name"].apply(normalize_function_name)

    merged_metric_data = scitools_df.merge(our_metric_df, on=['File', 'Name'], suffixes=("Scitools", "Srcml"))
    merged_metric_data.to_csv('SciToolsCompare' + csv_file_name + '.csv', index=False)

src_file = ".\\TheAlgorithms\\DataStructures\\Trees\\TrieImp.java"
#src_file = ".\\apache\\httpd-2.4.43\\support\\ab.c"
#src_file = ".\\Sokoban Pro\\Level.cs"

#root_dir = ".\\TheAlgorithms"
root_dir = ".\\Sokoban Pro"

file_name = src_file.split('\\')[-1]
# file_extension = src_file.split(".")[-1]
language = "C#"

srcml = get_srcml_from_path(src_file, language)

rootet = ET.fromstring(srcml)


local_function_names = _get_local_function_names(rootet)

enums = _get_enum_declarations(rootet)

#_calculate_metrics(rootet, language, local_function_names, enums, file_name)
_calculate_metrics_for_project(root_dir, 'sokobanPro.csv')
            
