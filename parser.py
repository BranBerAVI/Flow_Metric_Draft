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
    process = subprocess.run(["srcml", '--text', contents, "--language", language], check=True, text=True, capture_output=True) 
    return process.stdout

def get_srcml_from_path(path, language):
    process = subprocess.run(["srcml", path, "--language", language],  check=True, text=True, capture_output=True) 
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

    declaration_statements = element.findall(rf".//{{{SRC_NS}}}decl_stmt/")

    for child in declaration_statements:
        ele_sub_dict = {
            "specifier": "",
            "type": "",
            "modifier": "",
            "name": "",
            "signature": ""
        }
        
        for subel in child.iter(rf"{{{SRC_NS}}}decl"):
            subel_list = list(subel)

            name = [el.text if el.text else "" for el in subel_list if re.search(rf"{{{SRC_NS}}}name", str(el))][:1]

            ele_sub_dict["name"] = name[0]
            for child in subel.iter():                    
                if(re.search(rf".{{{SRC_NS}}}type" , str(child))):
                    for type_child in child:        
                        if(re.search(rf".{{{SRC_NS}}}specifier" , str(type_child))):
                            ele_sub_dict["specifier"] = type_child.text if type_child.text else ""

                        if(re.search(rf".{{{SRC_NS}}}name" , str(type_child))):
                            ele_sub_dict["type"] = type_child.text if type_child.text else ""

                        if(re.search(rf"{{{SRC_NS}}}modifier" , str(type_child))):
                            ele_sub_dict["modifier"] = type_child.text if type_child.text else ""

            if(ele_sub_dict["name"] != ""):
                ele_sub_dict["signature"] = re.sub(" +", " ", " ".join([ele_sub_dict["specifier"], ele_sub_dict["type"], ele_sub_dict["modifier"], ele_sub_dict["name"]]).rstrip())
                elestr_list.append(ele_sub_dict)
         
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

#Do not count calls that are passed in as a parameters to another call
#Not picking up all calls in a function!
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
    
    print(new_expr_list)
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

def _get_variables_read_from_expr(function, calls, function_declarations, pointer_declarations, params):
    fan_in = 0
    read_variable_names = []
    declarations = [decl["name"] for decl in [*pointer_declarations, *function_declarations]]
    params = [param["name"] for param in params]

    for child in function.iter():
        if(re.search(rf"{{{SRC_NS}}}expr_stmt", str(child))):
            expr = child.find(rf"{{{SRC_NS}}}expr")
            expr_name = expr.find(rf"{{{SRC_NS}}}name") if expr is not None else None
            expr_name_txt = expr_name.text if expr_name is not None else ""

            op = expr.find(rf"{{{SRC_NS}}}operator") if expr is not None else None
            op_txt = op.text if op is not None else ""

            expr_name_list = []

            if op_txt == "=":
                for el in expr.iter():
                    if re.search(rf"{{{SRC_NS}}}name", str(el)):
                        sub_expr_name_txt = el.text if el is not None else ""

                        if(sub_expr_name_txt != expr_name_txt):
                            expr_name_list.append(sub_expr_name_txt)

            read_variable_names = [*read_variable_names, *expr_name_list]

    read_variable_names = list(set([var for var in read_variable_names if var not in calls and var not in C_LIB_FUNCTIONS and var not in declarations and var is not None and var not in params and not re.match(r"^null$", var, flags=re.IGNORECASE)]))
    print(read_variable_names)
    fan_in = len(read_variable_names)

    #print(fan_in)
    return fan_in

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

def _calculate_metrics(rootet, file_definitions, src_file_path, language):
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
                
                expressions = _get_expr_signatures(child)
                declarations = _get_decl_signatures(child)            

                param_data = _get_pointers_from_parameter_list(child)
                pointer_decls = _get_pointer_declarations_from_expr(child)
                param_count = len(param_data["parameters"])

                macro_func_calls = _get_function_calls_from_macro_tags(child)

                #print(param_data["parameters"])

                calls = _get_unique_calls_from_function(child)  
                #print(calls)

                declaration_names = list(map(lambda decl: decl["name"], declarations))

                #Do not include functions that are declared within another function
                non_local_function_calls = list(filter(lambda call: call not in declaration_names, list(set([*calls, *macro_func_calls]))))
                
                if_expressions = _get_expr_from_conditional(child)
                #print(if_expressions)
                
                
                # print("Non Local Function Calls: ")
                # [print("    " + func) for func in non_local_function_calls]
                # print("|"*30)

                init_fan_out = _get_fan_out_from_expressions(declarations, expressions, if_expressions, param_data["parameters_passed_by_reference"], file_definitions, pointer_decls)
                #init_fan_in = _get_fan_in_from_expressions(declarations, expressions, if_expressions, param_data["parameters_passed_by_reference"], file_definitions, pointer_decls)

                
                init_fan_in = _get_variables_read_from_expr(child, calls, declarations, pointer_decls, param_data["parameters"])
                #print("read_var_names: ")
                print(init_fan_in)

                #print(init_metrics["fan_out"])
                print("----")
                
                #Add function to dict if not already in there
                if(func_sig not in list(function_dict)):
                    function_dict[func_sig] = {
                        "src_file": src_file,
                        "function_name": _get_name(child),
                        "param_count": param_count,
                        "is_void": True,
                        "functions_called_by": [],
                        "fan_in": param_count + init_fan_in,
                        "fan_out": init_fan_out + len(non_local_function_calls),
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
        # print ("Called by: ")
        # [print("    " + call) for call in functions_called_by]

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

file_definitions = _get_definitions_in_file(rootet)

_calculate_metrics(rootet, file_definitions, root_dir, language)
            

      




                


            
        



