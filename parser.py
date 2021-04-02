import xml.etree.ElementTree as ET
import re
import subprocess
import os
import sys
sys.setrecursionlimit(3000)

SRC_NS = 'http://www.srcML.org/srcML/src'
POS_NS = 'http://www.srcML.org/srcML/position'
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

def _is_pointer_declaration(element):
    decl = element.find(rf"{{{SRC_NS}}}decl")

    decl_init = decl.find(rf"{{{SRC_NS}}}init") if decl is not None else None
    decl_init_txt = decl_init.text if decl_init is not None and decl_init.text is not None else ""

    decl_type = decl.find(rf"{{{SRC_NS}}}type") if decl is not None else None
    decl_mod = decl_type.find(rf"{{{SRC_NS}}}modifier") if decl_type is not None else None
    decl_mod_txt = decl_mod.text if decl_mod is not None and decl_mod.text is not None else ""

    if decl_mod_txt == "*":
        return True
    
    return False

def _get_call_signature(element):
    call_sig = ""
    for substr in element.itertext():
        call_sig+=substr

    call_sig = re.sub(r"\s", "", call_sig)

    return call_sig

def _get_signature(element):
    def _join(values, delimiter=' '):
        return delimiter.join(i.strip() for i in values if i.strip())

    components = list()
    type_ = element.find('src:type', NS)
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

def _get_srcml(contents, language):
    try:
        args = ['srcml', '--position', '--language', language, '-o', "testxml.xml"]
        process = subprocess.run(
            args, input=contents, check=True, text=True, capture_output=True
        )
        return process.stdout
    except subprocess.CalledProcessError as error:
        print(error)
    return None

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

                decl_name = decl.find(rf"{{{SRC_NS}}}name") if decl is not None else None
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

                if type_name != "":
                    elestr_list.append({
                        "specifier": type_specifier_txt,
                        "type": type_name_txt,
                        "modifier": type_modifier_txt,
                        "name": decl_name_txt,
                        "index_tag": index_tag,
                        "index_str": index_str,
                        "signature": re.sub("/s+", " ", " ".join([type_specifier_txt, type_name_txt, type_modifier_txt, decl_name_txt]).rstrip())
                    })

            # for subel in child.iter(rf"{{{SRC_NS}}}decl"):
            #     subel_list = list(subel)

            #     name = [el.text if el.text else "" for el in subel_list if re.search(rf"{{{SRC_NS}}}name", str(el))][:1]

            #     ele_sub_dict["name"] = name[0]
            #     for child in subel.iter():                    
            #         if(re.search(rf".{{{SRC_NS}}}type" , str(child))):
            #             for type_child in child:        
            #                 if(re.search(rf".{{{SRC_NS}}}specifier" , str(type_child))):
            #                     ele_sub_dict["specifier"] = type_child.text if type_child.text else ""

            #                 if(re.search(rf".{{{SRC_NS}}}name" , str(type_child))):
            #                     ele_sub_dict["type"] = type_child.text if type_child.text else ""

            #                 if(re.search(rf"{{{SRC_NS}}}modifier" , str(type_child))):
            #                     ele_sub_dict["modifier"] = type_child.text if type_child.text else ""

            #     if(ele_sub_dict["name"] != ""):
            #         ele_sub_dict["signature"] = re.sub(" +", " ", " ".join([ele_sub_dict["specifier"], ele_sub_dict["type"], ele_sub_dict["modifier"], ele_sub_dict["name"]]).rstrip())
            #         elestr_list.append(ele_sub_dict)
         
    return elestr_list

def _get_definitions_in_file(root):
    definitions = []

    for child in root.iter():
        if(re.search(rf"define", str(child))):
            #parse the definition
            for define in child.iter():                
                if(re.search(rf"{{{SRC_NS}}}name", str(define))):
                    if(define.text):
                        definitions.append(define.text)
                    break

        elif (re.search(rf"typedef", str(child))):
            for define in child.iter():
                if(re.search(rf"{{{SRC_NS}}}decl", str(define))):
                   name = define.find(rf"{{{SRC_NS}}}name")
                   if(name is not None and name.text is not None):
                       definitions.append(name.text)

    return definitions

def _get_pointers_from_parameter_list(function):
    parameter_list = function.find(rf"{{{SRC_NS}}}parameter_list")
    parameters = parameter_list.findall(rf"{{{SRC_NS}}}parameter")

    parameter_declarations = []
    parameters_passed_by_reference = []

    for param in parameters:
        decl = param.find(rf"{{{SRC_NS}}}decl")  
        decl_name = decl.find(rf"{{{SRC_NS}}}name")
        decl_name_txt = decl_name.text if decl_name is not None and decl_name.text else ""

        decl_type = decl.find(rf"{{{SRC_NS}}}type")   
        decl_type_name = decl_type.find(rf"{{{SRC_NS}}}name")
        decl_type_name_txt = decl_type_name.text if decl_type_name is not None and decl_type_name.text else ""

        decl_type_modifier = decl_type.find(rf"{{{SRC_NS}}}modifier")   
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
            call_name_txt = call_name.text if call_name is not None and call_name.text is not None else ""


            if call_name_txt not in list(call_data):
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
            
            if(name is not None and name.text is not None):
                call_names.append(name.text)    


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

                if(decl_type_modifier_txt == "*"): #and decl_type_specifier_txt != "const"):
                    pointer_declarations.append({"type": decl_type_name_txt, "modifier": decl_type_modifier_txt, "name": decl_name_txt})

    # print("pointer decls: ")
    # print('♠'*20)
    # [print(decl) for decl in pointer_declarations]

    #print(pointer_declarations)
    return pointer_declarations

def _get_expr_from_conditional(function):
    expr_list = []

    for child in function.iter():
        if(re.search(rf"{{{SRC_NS}}}if_stmt", str(child))):
            if_contents = child.find(rf"{{{SRC_NS}}}if")
            if_condition = if_contents.find(rf"{{{SRC_NS}}}condition") if if_contents is not None else None
            if_expr = if_condition.find(rf"{{{SRC_NS}}}expr") if if_condition is not None else None

            expr_str = ""

            if(if_expr is not None):
                for el in if_expr:
                    if(el is not None and el.text is not None):
                        expr_str += el.text

            expr_split = re.split(r"\&\&|\|\|", expr_str)
            expr_list = [*expr_list, *expr_split]

    new_expr_list = []

    for expr in expr_list:
        if(not re.search(r"[a-zA-Z][a-zA-Z0-9]*(?<!\!)\=", expr) and not not re.search(r"[a-zA-Z][a-zA-Z0-9]*(?<!\=)\=", expr)):
            split_expr = re.split(r"\!\=|\>\=|\<\=|\=\=|\<|\>(?!\w)", expr)
            new_expr_list = [*new_expr_list, *split_expr]
    
    #print(new_expr_list)
    #filtered_expr = list(filter(lambda expr: expr is not None and re.match(r"\S\D", expr), new_expr_list))
    filtered_expr = [expr for expr in new_expr_list if expr is not None and re.match(r"\S\D", expr) and not re.search(r"[a-zA-Z][a-zA-Z0-9]*\=(?!\=)", expr)]
    #print(filtered_expr)
    return filtered_expr

def _get_fan_out_from_expressions(function_declaration_list, function_expression_list, if_expressions, parameters_passed_by_reference, file_definitions, pointer_declarations):
    fan_out = 0

    function_external_pointers = {}
    pointers = [*parameters_passed_by_reference, *pointer_declarations]

    pointer_names = [p["name"] for p in pointers]
    #print(pointer_names)

    for pointer in pointers:
        function_external_pointers[pointer["name"]] = {
            "reads": [],
            "writes": [],
            "direct_writes": []
        }

    #print (pointers)

    function_declaration_list_names = list(map(lambda func_decl: func_decl["name"], function_declaration_list))

    assignmentRegex = r"^\*?\w+\*?(=|->)[\w\W]+|(\*\w+|\w+\*)(\=|\+\=|\-\=|\+\+|\-\-|\*\=|\-\=)"
    incrementDecrementRegex = r"\*?\w+\*?((\+\+)|(\-\-)|(\+\=)|(\-\=)|(\*\=)|(\/\=))"
    #Match declarations/variable reassignments
    pointer_by_ref_names =  list(map(lambda param: param["name"], pointers))
    param_by_ref_counts = list(map(lambda param: {"name": param["name"], "read_count": 0, "write_count": 0}, parameters_passed_by_reference))
    #print (pointer_by_ref_names)

    fan_in_matches = []

    function_expression_list = [*function_expression_list, *if_expressions]

    #print(function_expression_list)

    #Find arithmetic operators
    for expr in function_expression_list:
        VarIsBeingAssigned = True if re.search(assignmentRegex, expr) else False
        VarIsBeingIncrOrDecr = re.search(incrementDecrementRegex, expr)

        fan_out_matches = []
        fan_out_matches_by_param = []
        split_var = []


        if(VarIsBeingAssigned):
            update_operators = r"=|\+\+|\-\-|\+\=|\-\=|\*\=|\/\="
            splitVar = re.split(update_operators, expr, 1) if re.search(update_operators, expr) else []

            leftHandSide = splitVar[0] if len(splitVar) else ""
            rightHandSide = splitVar[1] if len(splitVar) > 0 else ""   

            #print(expr)  

            if(len(splitVar) > 1):
                #Check lefthand side and see if it matches with any of the parameters passed by reference
                if(re.search(r"\-\>", leftHandSide)):
                    leftHandPointerCheck = re.split("->", leftHandSide)
                    leftHandPointer = leftHandPointerCheck[0]

                    if(len(leftHandPointerCheck) > 1):
                        if(leftHandPointer.rstrip() in pointer_by_ref_names):
                            # print(" left: " + str(leftHandPointer))
                            # print("right: " + str(leftHandPointerCheck[1]))
                            # print("altrt: " + str(rightHandSide))                            

                            rightHandMember = str(leftHandPointerCheck[1])
                            if(re.search(r"\w+\-\>\w+\[[\w\W]*\]?\=", str(expr))):
                                postPointerDereference = re.split(r"\-\>", str(expr), 1)[1]
                                #print("postp:" + postPointerDereference)
                                preEqualsPointerDereference = re.split(r"\=", str(postPointerDereference))[0] + ']'
                                #print("deref: " + preEqualsPointerDereference)

                                if(re.search(r"\[", rightHandMember)):
                                    rightHandMember = preEqualsPointerDereference
                            
                            #print('|' * 20)
                            #Find if left handside is in pointer list
                            if(leftHandPointer in list(function_external_pointers)):
                                pointer_members = function_external_pointers[leftHandPointer]["writes"]
                                pointer_members.append(rightHandMember)
                                pointer_members = list(set(pointer_members))
                                function_external_pointers[leftHandPointer]["writes"] = pointer_members
                                function_external_pointers[leftHandPointer]["writes"]
                elif(re.search(r"\*", leftHandSide)):                    
                    if(re.search(r"\*\*?[a-zA-Z][\w\d]*\=", str(expr))):
                        leftHandSideWithoutPointer = re.sub(r"\*|[^\w\d]", "", leftHandSide)                     
                        
                        if(leftHandSideWithoutPointer in list(function_external_pointers)):
                            pointer_members = function_external_pointers[leftHandSideWithoutPointer]["writes"]
                            pointer_members.append(rightHandSide)
                            pointer_members = list(set(pointer_members))
                            function_external_pointers[leftHandSideWithoutPointer]["writes"] = pointer_members
                else:
                    leftHandSideVar = re.sub(r"[^\w\d]", "", leftHandSide)
                   
                    if(leftHandSideVar in list(function_external_pointers)):                        
                        pointer_members = function_external_pointers[leftHandSideVar]["direct_writes"]
                        pointer_members.append(rightHandSide)
                        pointer_members = list(set(pointer_members))
                        function_external_pointers[leftHandSideVar]["direct_writes"] = pointer_members

            #Check if leftHandSide value is in any declarations
            fan_out_matches_sub = list(filter(lambda decl: decl["name"].rstrip() == leftHandSide.rstrip() and leftHandSide.rstrip() not in file_definitions, function_declaration_list))
            #fan_out_matches_by_param_sub = list(map(lambda param: param["name"], list(filter(lambda param: param["name"].rstrip() == leftHandSide.rstrip(), parameters_passed_by_reference))))
            
            fan_out_matches.append(fan_out_matches_sub)
            #fan_out_matches_by_param += fan_out_matches_by_param_sub
            
            #Divide the righthand side by any delimiters or rather, anything that isn't a word or number
            rightHandSideVariables = list(filter(lambda var: re.search("[^\d\s]", var) and var not in function_declaration_list_names and var not in file_definitions, re.split("[^\w\d]", rightHandSide)))
            fan_in_matches.extend(rightHandSideVariables)    


        #If the expression did not match any of the declarations within the function
        #Then someting outside of the function is being modified, so increment fan-out
        if(fan_out_matches == [] and len(split_var) > 1):
            fan_out+=1

    global_writes = 0
    for param in function_external_pointers:
        global_writes += len(function_external_pointers[param]["writes"]) + len(function_external_pointers[param]["direct_writes"])
        # print(" write: " + param )
        # [print ("    " + w) for w in function_external_pointers[param]["direct_writes"]]
        # print("dwrite: " + param )
        # [print ("    " + w) for w in function_external_pointers[param]["writes"]]
        # print("-"*10)
    
    fan_out += global_writes
    #Remove duplicates in fan-in matches
    fan_in_matches = list(set(fan_in_matches))

    #print("fan-out: " + str(fan_out))

    return fan_out

def _get_file_variable_declarations(root):
    declaration_names = []
    declarations = root.findall(rf"{{{SRC_NS}}}decl_stmt")

    for decl_stmt in declarations:
        decl = decl_stmt.find(rf"{{{SRC_NS}}}decl")
        decl_name = decl.find(rf"{{{SRC_NS}}}name")
        decl_name_txt = decl_name.text if decl_name is not None and decl_name.text is not None else ""

        if decl_name_txt != "":
            declaration_names.append(decl_name_txt)

    return declaration_names

def _get_enum_declarations(root):
    enum_names = []

    print("getting enums")
    for el in root.iter():
        if re.search(rf"{{{SRC_NS}}}enum", str(el)):
           
            enum_block = el.find(rf"{{{SRC_NS}}}block")
            enum_decls = enum_block.findall(rf"{{{SRC_NS}}}decl") if enum_block is not None else []

            for decl in enum_decls:
                decl_name = decl.find(rf"{{{SRC_NS}}}name")
                if decl_name is not None and decl_name.text is not None:
                    enum_names.append(decl_name)

    return list(set(enum_names))

def _get_variables_read_from_expr(function, calls, function_declarations, pointer_declarations, params, declarations, local_function_names, local_declarations, enums):
    fan_in = 0
    read_variable_names = []
    declarations = [decl["name"] for decl in [*pointer_declarations, *function_declarations]]
    params = [param["name"] for param in params]

    #print(declarations)
    call_args = []
    for call_name in list(calls):
        if calls[call_name]["cumulative_args"] != []:
            args = [arg for arg in calls[call_name]["cumulative_args"] if arg not in params and arg not in C_LIB_FUNCTIONS and arg not in C_LIB_STREAMS and arg not in C_RESERVED_KEYWORDS and arg not in declarations and arg not in local_function_names and not re.match(r"^null$", arg, flags=re.IGNORECASE) and arg not in enums]
            call_args = [*call_args, *args]

    for child in function.iter():
        if re.search(rf"{{{SRC_NS}}}expr_stmt", str(child)):
            expr = child.find(rf"{{{SRC_NS}}}expr")

            expr_descendants = list(expr.iter())


            expr_name = expr.find(rf"{{{SRC_NS}}}name") if expr is not None else None
            expr_name_txt = expr_name.text if expr_name is not None else ""

            ops = expr.findall(rf"{{{SRC_NS}}}operator") if expr is not None else None
            last_op = None
            #find last op that is =
            for op in ops:
                if op.text is not None and op.text == '=':
                    last_op = op

            op_txt = last_op.text if last_op is not None and last_op.text is not None else ""

            last_op_index = expr_descendants.index(last_op) if last_op is not None else 0
            
            read_expr = expr_descendants[last_op_index + 1:]
            

            if op_txt == "=" and last_op_index > 0:
                for el in read_expr:
                    if re.search(rf"{{{SRC_NS}}}name", str(el)):
                        sub_expr_name_txt = el.text if el is not None and el.text is not None else ""
                        
                        if(
                        sub_expr_name_txt != expr_name_txt and 
                        sub_expr_name_txt not in list(calls) and 
                        sub_expr_name_txt not in params and
                        sub_expr_name_txt not in call_args and
                        sub_expr_name_txt not in declarations and 
                        sub_expr_name_txt not in C_RESERVED_KEYWORDS and 
                        sub_expr_name_txt not in C_LIB_STREAMS and 
                        sub_expr_name_txt not in C_LIB_FUNCTIONS and
                        sub_expr_name_txt is not None and
                        sub_expr_name_txt not in local_function_names and
                        sub_expr_name_txt not in enums and
                        #sub_expr_name_txt not in local_declarations and
                        not re.match(r"^null$", sub_expr_name_txt, flags=re.IGNORECASE)):
                            read_variable_names.append(sub_expr_name_txt)
                            #print(sub_expr_name_txt)

        if re.search(rf"{{{SRC_NS}}}condition", str(child)):
            expr = child.find(rf"{{{SRC_NS}}}expr")            
            
            for el in expr.iter():
                if re.search(rf"{{{SRC_NS}}}name", str(el)):
                    sub_expr_name_txt = el.text if el is not None else ""

                    if(
                    sub_expr_name_txt not in list(calls) and 
                    sub_expr_name_txt not in params and
                    sub_expr_name_txt not in call_args and
                    sub_expr_name_txt not in declarations and 
                    sub_expr_name_txt not in C_RESERVED_KEYWORDS and 
                    sub_expr_name_txt not in C_LIB_STREAMS and 
                    sub_expr_name_txt not in C_LIB_FUNCTIONS and
                    sub_expr_name_txt is not None and
                    sub_expr_name_txt not in local_function_names and
                    sub_expr_name_txt not in enums and
                    #sub_expr_name_txt not in local_declarations and
                    not re.match(r"^null$", sub_expr_name_txt, flags=re.IGNORECASE)):
                        read_variable_names.append(sub_expr_name_txt)

    read_variable_names = list(set([*read_variable_names, *call_args]))
    #print(read_variable_names)
    fan_in = fan_in + len(read_variable_names)

    # print(fan_in)

    # print("var reads: ")
    # total_reads = sorted(read_variable_names)
    # [print(read) for read in total_reads]

    
    # print('_'*30)
    return fan_in

def _get_name_from_nested_name(name):
    if name is not None:
        if name.text is not None:
            return name
        elif name.find(rf"{{{SRC_NS}}}name") is not None:
            next_name = name.find(rf"{{{SRC_NS}}}name")
            _get_name_from_nested_name(next_name)

    return None

def _get_variable_writes_from_expr(function, expressions, function_declaration_list, parameters_passed_by_reference, file_definitions, pointer_declarations, calls):
    fan_out = 0

    variable_writes = {
        
    }

    function_external_pointers = {}

    decl_names = [d["name"] for d in [*function_declaration_list, *pointer_declarations]]

    pointers = [*parameters_passed_by_reference, *pointer_declarations]

    pointer_names = [p["name"] for p in pointers]

    for expr in expressions:        
        expr_children = [child for child in expr.iter()]     
        expr_str = ''.join([child for child in expr.itertext()])     

        expr_names = expr.findall(rf"{{{SRC_NS}}}name")
        operators = expr.findall(rf"{{{SRC_NS}}}operator")

        equals_op = next((op for op in operators if op is not None and op.text is not None and re.fullmatch(rf"^\=|\+\=|\-\=|\*\=|\\\=$", op.text)), None)
        equals_op_pos = equals_op.attrib[rf"{{{POS_NS}}}start"].split(':') if equals_op is not None and rf"{{{POS_NS}}}start" in equals_op.attrib.keys() else [-1, -1]
        equals_op_row = int(equals_op_pos[0])
        equals_op_col = int(equals_op_pos[1])

        last_op = operators[-1] if len(operators) > 0 else None
        last_op_txt = last_op.text if last_op is not None and last_op.text is not None else ''

        last_op_pos = last_op.attrib[rf"{{{POS_NS}}}start"].split(':') if last_op is not None else [-1, -1]
        last_op_pos_row = int(last_op_pos[0])
        last_op_pos_col = int(last_op_pos[1])

        fan_out_var_candidates = []

        if last_op_txt != '':
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
                        
                        expr_sub_index = name.find(rf"{{{SRC_NS}}}index")  
                        expr_sub_index_txt = ''.join(child_txt for child_txt in expr_sub_index.text if expr_sub_index.text is not None) if expr_sub_index is not None else ''                       

                        first_expr_name_txt = expr_sub_name.text if expr_sub_name is not None and expr_sub_name.text is not None else ''.join([child_txt for child_txt in first_expr_name.itertext()])
                        name_signature = ''.join([child_txt for child_txt in name.itertext()])
                        
                        name_op = name.findall(rf"{{{SRC_NS}}}operator")
                        member_access_op = next((op for op in name_op if op is not None and op.text is not None and op.text == '->'), None)
                        member_access_op_pos = member_access_op.attrib[rf"{{{POS_NS}}}start"].split(':') if member_access_op is not None and rf"{{{POS_NS}}}start" in member_access_op.attrib.keys() else [-1, -1]
                        member_access_op_pos_row = int(member_access_op_pos[0])
                        member_access_op_pos_col = int(member_access_op_pos[1])

                        members_accessed = []
                        expr_mod_statements = []

                        if (member_access_op is not None 
                            and member_access_op_pos_row == expr_sub_name_pos_row 
                            and member_access_op_pos_col > expr_sub_name_pos_col 
                            and member_access_op_pos_col < equals_op_row 
                            and member_access_op_pos_row == equals_op_row):
                            for child in expr_sub_names:
                                child_pos = child.attrib[rf"{{{POS_NS}}}start"].split(':') if rf"{{{POS_NS}}}start" in child.attrib.keys() else [-1, -1]
                                child_pos_row = int(child_pos[0])
                                child_pos_col = int(child_pos[1])

                                if child_pos_row == member_access_op_pos_row and child_pos_col > member_access_op_pos_col:
                                    members_accessed.append(_get_name_from_nested_name(child).text)
                        elif member_access_op is None and expr_sub_index is None: 
                            expr_mod_statements.append(expr_str)

                        if first_expr_name_txt in pointer_names or first_expr_name not in decl_names:
                            fan_out_var_candidates.append({
                            "name": first_expr_name_txt,
                            "signature": name_signature,
                            "row_pos": name_pos_row,
                            "col_pos": name_pos_col,
                            "members_accessed": members_accessed,
                            "indices" : [expr_sub_index_txt],
                            "expr_mod_statements": expr_mod_statements
                            })  

            for cand in fan_out_var_candidates:           
                if re.fullmatch(r"^\=|\+\=|\-\=|\*\=|\\\=$", last_op_txt) and last_op_pos_col > cand["col_pos"] and last_op_pos_row == cand["row_pos"]:
                    
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
                elif re.fullmatch(r"^\+\+|\-\-$", last_op_txt) and last_op_pos_row == cand["row_pos"]:
                    
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

    for key in list(variable_writes):
        # print("variable: " + key)
        # print("expressions: ")
        for expr in variable_writes[key]['expressions']:
            #print("    " + expr)

            if len(variable_writes[key]['expressions']) > 0:
                fan_out += 1

            fan_out += len(variable_writes[key]['members_modified']) + len(variable_writes[key]['indices_modified'])

        # print("\nmodified members:")
        # for mem in variable_writes[key]['members_modified']:
        #     print('    ' + mem)

        # print("\nmodified indices:")
        # for indx in variable_writes[key]['indices_modified']:
        #     print('   ' + indx)       


        #print ('\n')
    print("New Fan Out: " + str(fan_out))
        
    return fan_out

def _get_fan_in_from_expressions(function_declaration_list, function_expression_list, if_expressions, parameters_passed_by_reference, file_definitions, pointer_declarations):
    fan_in = 0

    function_external_pointers = {}
    declarations = [decl["name"] for decl in [*pointer_declarations, *function_declaration_list]]

    expressions = [*function_expression_list, *if_expressions]

    #print(expressions)
    #print(declarations)

    for expr in expressions:
        if(re.search(r"[a-zA-Z][a-zA-Z0-9]*(?<!\!)\=(?!\=)", expr) or re.search(r"[a-zA-Z][a-zA-Z0-9]*(\-\>)[a-zA-Z][a-zA-Z0-9]*(?<!\!)\=(?!\=)", expr)):
            split_expr = re.split(r"(?<!\!)\=(?!\=)", expr, 1)
            
            if(len(split_expr) > 1):
                left_expr = split_expr[0]
                right_expr = split_expr[1]

                #print(expr)
    
    return fan_in

def _get_fan_in(function_metrics, src_file_path, language):
    other_file_functions = {src_file_path: {
        "functions_called_by": {}
    }}    

    #print ("function names: ")
    #[print(function_metrics[func]["function_name"]) for func in list(function_metrics)]
    extension = "c" if language == "C" else "cpp" if language == "C++" else "java" if language == "JAVA" else "cs" if language == "C#" else ""
    
    fan_in_log = open("fan_in.log", "w")
    fan_in = 0

    # if(extension != ""):
    #     #Now its time to search to see how procedures in the current file are used elswhere in the current project
    #     print("fan in ops: ")
    #     for root, dirs, files in os.walk(root_dir):
    #         for file in files:
    #             if(file.endswith(extension)):
    #                 current_file_path = os.path.join(root, file)

    #                 #print(current_file_path)
                    
    #                 #Do not measure metrics for the same file twice
    #                 #Also have to see if the src_file is being imported 
    #                 #and used in this file
    #                 if(current_file_path != src_file_path):
    #                     #Run the current file data through srcml
    #                     srcml = get_srcml_from_path(current_file_path, language)
    #                     root_file = ET.fromstring(srcml)

    #                     #We only have to measure the calls 
    #                     for child in root_file.iter():                   
    #                         #increment the fan-in of the called function
    #                         if(re.search(rf'{{{SRC_NS}}}function', str(child))):
    #                             func_name = child.find(rf"{{{SRC_NS}}}name")
    #                             func_name_txt = func_name.text if func_name is not None and func_name.text is not None else ""

    #                             if(func_name_txt != ""):
    #                                 for subel in child.iter():
    #                                     if(re.search(rf'{{{SRC_NS}}}call', str(subel))):
    #                                         call_sig = _get_call_signature(subel)
    #                                         #print(call_sig)           

    #                                         call_arg_list = subel.find(rf"{{{SRC_NS}}}argument_list")     
    #                                         call_args = call_arg_list.findall(rf"{{{SRC_NS}}}argument") if call_arg_list is not None else []
    #                                         call_name = subel.find(rf"{{{SRC_NS}}}name")
    #                                         call_name_txt = call_name.text if call_name is not None else ""   
                                            
    #                                         call_name_matches = [function for function in list(function_metrics)]

    #                                         for function in list(function_metrics):
    #                                             if function_metrics[function]['function_name'] == call_name_txt:
    #                                                 call_name_matches.append(function)
    #                                                 function_path = (current_file_path + "\\" + func_name_txt)
    #                                                 function_metrics[function]['functions_called_by'].append(function_path[2:])
    #                                                 function_metrics[function]['functions_called_by'] = list(set(function_metrics[function]['functions_called_by']))

    #                                         if(call_name_matches != []):
    #                                             fan_in_log.write(call_sig + '\n')
    #                                             fan_in_log.write(str(call_name_matches) + '\n')
    #                                             fan_in_log.write('_'*30 + '\n')

                                        
    fan_in_log.close()

def _get_file_imports(path):
    pass

def _calculate_metrics(rootet, file_definitions, src_file_path, language, local_function_names, local_declarations, enums):
    function_dict = {}

    definitions = {}
    declarations = {}
    #print(rootet)

    for child in rootet.iter():
        #print(child)
        # if(re.search(rf"{{{SRC_NS}}}literal", str(child))):
        #     _parse_literal_for_functions(child, language)

        if(re.search(rf"{{{SRC_NS}}}function", str(child))):
            #Do not analyze function prototypes. Only perform analysis on functions that have blocks of code in them
            block = child.find(rf"{{{SRC_NS}}}block")

            if(block is not None):
                func_sig = _get_signature(child)                

                print(func_sig)
                current_function = func_sig
                
                expression_signatures = _get_expr_signatures(child)
                expressions = _get_exprs_from_function(child)
                declarations = _get_decl_signatures(child)         

                param_data = _get_pointers_from_parameter_list(child)
                pointer_decls = _get_pointer_declarations_from_expr(child)
                param_count = len(param_data["parameters"])

                
                macro_func_calls = _get_function_calls_from_macro_tags(child)

                #print(param_data["parameters"])

                calls = _get_all_function_call_info(child)                
        
                declaration_names = list(map(lambda decl: decl["name"], declarations))
                
                #print(declaration_names)

                #Do not include functions that are declared within another function
                non_local_function_calls = list(filter(lambda call: call not in declaration_names and call not in C_LIB_FUNCTIONS, list(set([*list(calls), *macro_func_calls]))))

                if_expressions = _get_expr_from_conditional(child)
                #print(if_expressions)               
                # print("Non Local Function Calls: ")
                # [print("    " + func) for func in non_local_function_calls]
                # print("|"*30)
                #(function, expressions, function_declaration_list, function_expression_list, if_expressions, parameters_passed_by_reference, file_definitions, pointer_declarations):
    

                init_fan_out = _get_fan_out_from_expressions(declarations, expression_signatures, if_expressions, param_data["parameters_passed_by_reference"], file_definitions, pointer_decls)

                #if re.search(r"close_connection", func_sig):
                writes_fan_out = _get_variable_writes_from_expr(child, expressions, declarations, param_data["parameters_passed_by_reference"], file_definitions, pointer_decls, calls)
                
                init_fan_in = _get_variables_read_from_expr(child, calls, declarations, pointer_decls, param_data["parameters"], declarations, local_function_names, local_declarations, enums)
                #print("read_var_names: ")
                #print(init_fan_in)

                #print(init_metrics["fan_out"])
                print("--------------------------")
                
                #Add function to dict if not already in there
                if func_sig not in list(function_dict):
                    function_dict[func_sig] = {
                        "src_file": src_file,
                        "function_name": _get_name(child),
                        "param_count": param_count,
                        "is_void": True,
                        "functions_called_by": [],
                        "fan_in": param_count + init_fan_in,
                        "fan_out": writes_fan_out + len(non_local_function_calls),
                        "paths": 1,
                        "has_return": False,
                        "return_counted": False
                    }

                #Keep iterating through to get function contents
                #After this block, the fan-in, fan-out, and paths metrics
                #will have been calculated for contents within the current file.
                #
                #We will also have to analyze the function for external variables 
                #as well in order to determine if this function has executed a
                #global variable read, or a global variable write
                for subel in child.iter():
                    if(re.search(rf'{{{SRC_NS}}}return', str(subel)) and function_dict[current_function]["return_counted"] == False):  
                        return_expr = subel.find(rf"{{{SRC_NS}}}expr")

                        if(return_expr is not None):
                            function_dict[current_function]["has_return"] = True       

                    if(re.search(rf'{{{SRC_NS}}}(\bif\b|\belse\b|\btry\b|\bcatch\b|\bthen\b|\bcase\b|\bdefault\b)', subel.tag)):
                        function_dict[current_function]["paths"] += 1

                if (function_dict[current_function]["has_return"] and function_dict[current_function]["return_counted"] is False):
                    function_dict[current_function]["fan_out"] += 1
                    function_dict[current_function]["return_counted"] = True
                    
    _get_fan_in(function_dict, src_file_path, language)
                  

    #Display metric results
    for key in list(function_dict):
        function_dict[key]["fan_in"] = function_dict[key]["fan_in"] + len(function_dict[key]["functions_called_by"])
        fan_in = function_dict[key]["fan_in"]
        fan_out = function_dict[key]["fan_out"]
        functions_called_by = function_dict[key]["functions_called_by"]
        paths = function_dict[key]["paths"]
        flow = (fan_in * fan_out)**2

        print ('-'*30)
        print (" Func Sig: " + key)
        print ("   Fan-in: " + str(fan_in))
        print ("  Fan-out: " + str(fan_out))
        print ("    Paths: " + str(paths))
        print ("     Flow: " + str(flow))
        print ("Called by: ")
        [print("    " + call) for call in functions_called_by]

src_file = ".\\apache\\httpd-2.4.43\\support\\ab.c"
#src_file_path = ".\\gitahead\\dep\\libgit2\\libgit2\\src\\xdiff\\xdiffi.c"
root_dir = ".\\apache\\httpd-2.4.43"
file_extension = src_file.split(".")[-1]
language = "C"

# file=open(src_file, "r")
# contents = file.read()
# file.close()

#print(contents)
srcml = get_srcml_from_path(src_file, language)

rootet = ET.fromstring(srcml)

local_function_names = _get_local_function_names(rootet)
local_declarations = _get_file_variable_declarations(rootet)

file_definitions = _get_definitions_in_file(rootet)

enums = _get_enum_declarations(rootet)

_calculate_metrics(rootet, file_definitions, root_dir, language, local_function_names, local_declarations, enums)
            
