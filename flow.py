import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element as ElementTreeElement
import flow_parser as parser
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


NEWLINE_RE = re.compile(r'\r\n?|\n')

def _count_fan_in(global_variable_reads):
    return len(global_variable_reads)

def _count_fan_out(variable_writes):
    fan_out = 0

    print_data = False
    for key in list(variable_writes):        
        if len(variable_writes[key]['expressions']) > 0:
            fan_out += 1

        var_expressions = [e for e in variable_writes[key]['expressions'] if e.rstrip() != '']
        members_modded = list(set([m for m in variable_writes[key]['members_modified'] if m.rstrip() != '']))
        indicies_modded = list(set([i for i in variable_writes[key]['indices_modified'] if i.rstrip() != '']))

        fan_out += len(members_modded) + len(indicies_modded)

        if print_data:
            print("variable: " + key)
            print("expressions: ")
            for expr in var_expressions:
                print("    " + expr)


            print("\nmodified members:")
            for mem in members_modded:
                print('    ' + mem)

            print("\nmodified indices:")
            for indx in indicies_modded:
                print('   ' + indx)       

    return fan_out

def _reformat_acyclical_paths_tree(acyc_paths):
    npath_chains = []
    current_chain = []
    
    pos = 0

    for path in acyc_paths:
        #print (path)
        if isinstance(path, dict):
            p_children = path["children"] if "children" in path.keys() else []
            p_type = path["type"] if "type" in path.keys() else ""
            p_element = path["element"] if "element" in path.keys() else []

            if re.fullmatch(rf"{{{SRC_NS}}}if", p_element.tag):# == "if_stmt":
                p_if_type = path["if_type"]

                if p_if_type != '':
                    npath_chains.append(p_if_type)    
                else:
                     npath_chains.append('if') 
            elif re.fullmatch(rf"{{{SRC_NS}}}(for|while)", p_element.tag):
                npath_chains.append('loop')
            elif re.fullmatch(rf"{{{SRC_NS}}}else", p_element.tag):
                npath_chains.append('else')   
            elif re.fullmatch(rf"{{{SRC_NS}}}switch", p_element.tag):
                npath_chains.append('switch')
            elif re.fullmatch(rf"{{{SRC_NS}}}case", p_element.tag):
                npath_chains.append('case')
            elif re.fullmatch(rf"{{{SRC_NS}}}default", p_element.tag):
                npath_chains.append('default')         
            
            if len(p_children) > 0:
                p_children_dataset = _reformat_acyclical_paths_tree(acyc_paths = p_children)
                if p_children_dataset != []:
                    npath_chains.append(p_children_dataset)

        elif isinstance(path, str) and path == "break":
            #npath_chains.append(current_chain)
            #print(current_chain)
            npath_chains.append('break')
            #current_chain = []  

        pos += 1

    #npath_chains.append(current_chain)
    return npath_chains

def _count_npath_from_reformatted_acyclical_paths_tree(formatted_acyc_paths, current_depth = 0):
    npath = 0
    local_npath = 0
    pos = 0

    while pos < len(formatted_acyc_paths):
        prev = formatted_acyc_paths[pos - 1] if pos > 0 else 'break'
        current = formatted_acyc_paths[pos]

        next_el = formatted_acyc_paths[pos + 1] if pos + 1 < len(formatted_acyc_paths) else []
        next_el_over = formatted_acyc_paths[pos + 2] if pos + 2 < len(formatted_acyc_paths) else 'break'
        # next_el_over = formatted_acyc_paths[pos + 2] if pos + 2 < len(formatted_acyc_paths) else 'break'

        npath_child = _count_npath_from_reformatted_acyclical_paths_tree(next_el, current_depth = current_depth + 1) if isinstance(next_el, list) else 1
        #npath_child = 1 if npath_child == 0 else npath_child

        if isinstance(current, str):
            previous_is_valid = False

            if pos > 0:
                for el in reversed(formatted_acyc_paths[:pos]):
                    if isinstance(el, str):
                        if re.fullmatch(r'^if|elseif|else|loop|switch$', el):
                            previous_is_valid = True
                            break
                        elif el == 'break':
                            previous_is_valid = False
                            break

            if current == 'if':
                next_el_over = formatted_acyc_paths[pos + 2] if pos + 2 < len(formatted_acyc_paths) else 'break'
                previous_over = formatted_acyc_paths[pos - 2] if pos - 2 >= 0 else 'break'

                proceded_by_else = True if isinstance(next_el_over, str) and re.fullmatch(r'$(else|elseif)^', next_el_over) else False
                preceded_by_else = False                
                
                if next_el_over == 'elseif' or next_el_over == 'else':
                    npath += 1 + npath_child
                elif (isinstance(previous_over, str) and re.fullmatch(r'^if|switch|loop$', previous_over)):                    
                    if npath_child == 0:
                        npath = npath + 2 if npath == 0 else npath * 2
                    else:
                        npath = npath + (2 * npath_child) if npath == 0 else npath * 2 * npath_child
                else:# isinstance(next_el_over, str) and next_el_over == 'break':
                    npath = npath + 2 * npath_child if npath_child > 0 else npath + 2 

            elif current == 'elseif':
                npath += 1 + npath_child               
            elif current == 'else':
                preceded_by_if_else = False
                npath += 1 + npath_child
  
            elif current == 'loop':
                previous_over = formatted_acyc_paths[pos - 2] if pos - 2 >= 0 else 'break'
                # print('loop')
                # print(npath_child)
                if isinstance(previous_over, str) and re.fullmatch(r'^if|elseif|else|loop|switch$', previous_over):
                    npath = npath * (1 + npath_child) if npath_child > 0 else npath * 2
                else:
                    npath = npath + 1 + npath_child if npath_child > 0 else npath + 2                             

            elif current == 'switch':
                npath += 1 + npath_child
            elif current == 'case':
                npath += 1 + npath_child
            elif current == 'default':
                npath += npath_child

        pos += 1
        
        # print(('-'*current_depth) + "  current inst: " + str(current))
        # print(('-'*current_depth) + " current npath: " + str(npath))
        # print('\n')

    if current_depth == 0 and npath == 0:
        npath += 1

    return npath

def _calculate_metrics(rootet, language, local_function_names, enums, file_name):
    #function_dict = {}
    all_local_call_names = []
    #classinator(rootet)

    parent_declarations = [parser._parse_declaration(element = decl, parent_struct_name = "file", parent_struct_type = "", belongs_to_file = file_name) for decl in rootet.findall(rf"{{{SRC_NS}}}decl_stmt")]

    function_dict = parser._parse_functions_for_global_variable_operations_and_acyclical_paths(
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
        function_dict[key]["called_by"] = locally_called_by
        calls = function_dict[key]["calls"]

        #function_dict[key]["fan_in"] += len(locally_called_by)
        name = function_dict[key]["function_name"]
        file_name = function_dict[key]["file_name"]
        func_parent_name = function_dict[key]["parent_structure_name"]
        func_parent_type = function_dict[key]["parent_structure_type"]
        has_return = 1 if function_dict[key]["has_return"] else 0
        fan_in = _count_fan_in(function_dict[key]["global_variable_reads"]) + len(locally_called_by) 
        fan_out = _count_fan_out(function_dict[key]["global_variable_writes"]) + len(list(calls)) + has_return

        acyc_paths_tree = function_dict[key]["acyclical_paths_tree"]
        reformatted_acyc_paths = _reformat_acyclical_paths_tree(acyc_paths_tree)
        npath = _count_npath_from_reformatted_acyclical_paths_tree(reformatted_acyc_paths)

        function_dict[key]["fan_in"] = fan_in
        function_dict[key]["fan_out"] = fan_out
        function_dict[key]["npath"] = npath
        
        functions_called_by = function_dict[key]["functions_called_by"]
        acyclical_path_tree = function_dict[key]["acyclical_paths_tree"]
        flow = (fan_in * fan_out)**2
        

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
    merged_metric_data = merged_metric_data.drop_duplicates(subset = ['File', 'Name']).sample(n=333)
    merged_metric_data.to_csv('SciToolsCompare' + csv_file_name + '.csv', index=False)

def _calculate_metrics_for_functions_in_file(root, file_name, function_name):
    
    for subdir, dirs, files in os.walk(root):
        for file in files:
            
            if file == file_name:
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
                    srcml = parser.get_srcml_from_path(path, language)
                    root = ET.fromstring(srcml)

                    local_function_names = parser._get_local_function_names(root)
                    enums = parser._get_enum_declarations(root)
                    
                    function_dict = _calculate_metrics(rootet = root, language = language, local_function_names = local_function_names, enums = enums, file_name = file)

                    for key in function_dict.keys():
                        name = function_dict[key]["function_name"]
                        
                        if name == function_name:
                            print( "    Path: " + path)
                            print ("    File: " + file_name)
                            print ("Function: " + name)
                            file_name = function_dict[key]["file_name"]
                            func_parent_name = function_dict[key]["parent_structure_name"]
                            func_parent_type = function_dict[key]["parent_structure_type"]
                            fan_in = function_dict[key]["fan_in"]
                            fan_out = function_dict[key]["fan_out"]
                            npath = function_dict[key]["npath"]
                            functions_called_by = function_dict[key]["functions_called_by"]                            
                            calls = function_dict[key]["calls"]
                            called_by = function_dict[key]["called_by"]
                            global_writes = function_dict[key]["global_variable_writes"]
                            global_reads = function_dict[key]["global_variable_reads"]
                            param_count = function_dict[key]["param_count"]                        

                            print ("\n      Fan-in: " + str(fan_in))
                            print ("     Fan-out: " + str(fan_out))
                            print ("       Paths: " + str(npath))
                            print (" Param Count: " + str(param_count))

                            print ("\nGlobal Variable Writes: ")
                            for key in global_writes.keys():
                                print (key)
                                print ("    Expressions: ")
                                for e in global_writes[key]["expressions"]:
                                    print ("          " + str(e))

                                print ("        Indices: ")
                                for i in global_writes[key]["indices_modified"]:
                                    print ("          " + str(i))

                                print ("        Members: ")
                                for m in global_writes[key]["members_modified"]:
                                    print ("          " + str(m))
            
                            print ("\nGlobal Variable Reads: ")
                            [print("    " + str(r)) for r in global_reads]

                            print ("Calls to: ")
                            [print("    " + str(c)) for c in calls]

                            print ("Called by: ")
                            [print("    " + str(c)) for c in called_by]

                            print('-'*30)


#src_file = ".\\TheAlgorithms\\DataStructures\\Trees\\TrieImp.java"
src_file = ".\\apache\\httpd-2.4.43\\support\\ab.c"
#src_file = ".\\Sokoban Pro\\Level.cs"
#src_file = ".\\"
#src_file = ".\\apache\\httpd-2.4.43\\modules\\loggers\\mod_log_config.c" #ab.c""

root_dir = ".\\apache"
#root_dir = ".\\Sokoban Pro"
#root_dir = ".\\apache"

file_name = src_file.split('\\')[-1]
# file_extension = src_file.split(".")[-1]
language = "C"

srcml = parser.get_srcml_from_path(src_file, language)

rootet = ET.fromstring(srcml)


local_function_names = parser._get_local_function_names(rootet)
enums = parser._get_enum_declarations(rootet)

#_calculate_metrics(rootet, language, local_function_names, enums, file_name)
#_calculate_metrics_for_project(root_dir, 'apache.csv')
_calculate_metrics_for_functions_in_file(root = root_dir, file_name = "mod_authz_user.c", function_name = "user_parse_config")           
