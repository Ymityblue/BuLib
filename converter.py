import ast
import inspect
import astunparse

from sympy import *
from sympy.physics.units import *

class Variable_Collector(ast.NodeVisitor):
    def __init__(self):
        self.variables = {}
    def visit_Assign(self, node: ast.Assign):
        def convert_Store_to_Load(name):
            name.ctx = ast.Load()
            return name

        for target in node.targets:
            if isinstance(target, ast.Tuple):
                ids = [name for name in target.elts]
                values = [val for val in node.value.elts]
                iterator = 0
                try:
                    while iterator < len(ids):
                        self.variables[convert_Store_to_Load(ids[iterator])] = values[iterator]
                        iterator += 1
                except Exception as inst:
                    if type(inst) == ValueError:
                        raise ValueError("Unequal Tuples") from inst
                    else:
                        raise Exception(inst)
            elif isinstance(target, ast.Name):
                self.variables[convert_Store_to_Load(target)] = node.value

class Tree_transformer(ast.NodeTransformer):
    def __init__(self, variables, Readable = False, Include_Constants= False):
        self.Readable = Readable
        self.Include_Constants = Include_Constants
        self.variables = variables
        self.replacement = self.Generate_replacement_table()

    def check_type(self, replacement:dict, value):
        def indentical(value, replacement_value):
            if isinstance(value, ast.Constant): 
                return False
            return value.id == replacement_value.id and type(value.ctx) is type(replacement_value.ctx)
        
        #replace() 
        if isinstance(value, ast.Name):
            #replacefunction 
            while len(replacement) > 0: 
                name = list(replacement.keys())[0]
                if indentical(value, name):
                    if self.Readable:
                        print(ast.dump(value), "->", ast.dump(replacement[name]), "\n")
                    return replacement[name]
        
                del replacement[name]
        elif isinstance(value, ast.Tuple):
            value.elts = [self.check_type(replacement, val) for val in value.elts]
        elif isinstance(value, ast.Call):
            value.args = [self.check_type(replacement, val) for val in value.args]
        elif isinstance(value, ast.BinOp):
            value.left = self.check_type(replacement, value.left)
            value.right = self.check_type(replacement, value.right)
        elif isinstance(value, ast.Constant):
            pass
        else:
            raise Exception("Nonimplemented operation detected : ", type(value))
        #return the 
        return value
    
    def Generate_replacement_table(self): 
        def constant_tree(tree, variables):
            #print(ast.dump(tree))
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    for j in variables:
                        if node.id == j.id:
                            return False
            return True

        #copy variables
        replacement = self.variables.copy()
        #reverse variables
        temp_replacement = {}
        for i in reversed(replacement):
            temp_replacement[i] = replacement[i]
        replacement = temp_replacement 
        #remove constats
        if not self.Include_Constants:
            for i in self.variables:
                #check if all variables are constats
                if constant_tree(self.variables[i], self.variables):
                    del replacement[i]

        i = 0
        keys = list(replacement.keys())
        while i < len(replacement):
            temp_replacement = replacement.copy()
            replacement[keys[i]] = self.check_type(temp_replacement, replacement[keys[i]])
            i += 1
        return replacement

    def visit_Assign(self, node: ast.Assign):
        if self.Readable:
            print("-"*20 + " visit_Assign " + "-"*20 + "\n")
            for i in self.replacement:
                print(ast.dump(i),"\n\t", ast.dump(self.replacement[i]))
        #substitute tree
        temp_replacement = self.replacement.copy()
        node.value = self.check_type(temp_replacement, node.value)
        return node    

    def visit_Return(self, node: ast.Return):
        if self.Readable:
            print("-"*20 + " visit_Return " + "-"*20 + "\n")
            print(ast.dump(node, indent = 4))
        #add sumpy.simplify
        node.value = ast.Call(
            func=ast.Name(id='simplify', ctx=ast.Load()),
            args=[node.value],
            keywords=[
                ast.keyword(
                    arg='evaluate',
                    value=ast.Constant(value=False))])
        #substitute tree
        temp_replacement = self.replacement.copy()
        node.value = self.check_type(temp_replacement, node.value)
        return node


class Tree_chopper():
    def __init__(self, func, Readable = False, Include_Constants = False):
        self.func = func
        self.Readable_tracker = None
        self.Readable(Readable)
        self.Include_Constants = Include_Constants

        self.source = inspect.getsource(self.func)
        self.changed_tree = None
        self.tree = ast.parse(self.source)

        if self.Readable():
            print("Function: ", self.func.__name__, " initialized\n" ,self.source)
        
        #collect variables
        VarCollector = Variable_Collector()
        VarCollector.visit(self.tree)
        self.variables = VarCollector.variables
        
        #clean up the code 
        self.substitue()
        self.clean()
        


        #get the remaining variables
        VarCollector.variables = {}
        VarCollector.visit(self.changed_tree)
        self.variables = VarCollector.variables
        var_id = [i.id for i in self.variables]
        
        
        #WARNING! 
        #this does not work if the return isn't at the bottom of the Function
        #this does not work if there are multiple return
        #this does not handle complex code just arithmatic
        #not that it was indened to

        #retreve simplified awnser
        #print("def " + self.func.__name__ + 
        #    "():\n    " + " ".join(var_id) + " = symbols(\"" + ",".join(var_id) + "\")\n"+ 
        #    "".join((str(self).split("\n"))[-2]) +
        #    "\nretreve = ("+self.func.__name__+"())")
        loc = {}
        exec("def " + self.func.__name__ + 
            "():\n    " + " ".join(var_id) + " = symbols(\"" + ",".join(var_id) + "\")\n"+ 
            "".join((str(self).split("\n"))[-2]) +
            "\nretreve = ("+self.func.__name__+"())", globals(), loc)
        self.simplifiedexpr = loc["retreve"]
        #print(ast.dump(ast.parse(str(self.simplifiedexpr)), indent = 4))
        
        for node in ast.walk(ast.parse(str(self.simplifiedexpr))):
            if isinstance(node, ast.Expr):
                return_expr_val = node.value
                break

        for node in ast.walk(self.changed_tree):
            if isinstance(node, ast.Return):
                node.value = return_expr_val
                break
                #print(ast.dump(node, indent = 4))
        

        #TODO
        #count segnificant
        #output

    def Readable(self, *args) -> bool:
        if len(args) > 0:
            if type(args[0]) == tuple:
                args[0] = list(args[0])
            self.Readable_tracker = args[0]
        else:
            if type(self.Readable_tracker) in [list, tuple]:
                t = self.Readable_tracker[0]
                del self.Readable_tracker[0]
                return t
            else:
                return self.Readable_tracker
        return False
    
    def substitue(self, Include_Constants= None):
        if Include_Constants == None:
            Include_Constants = self.Include_Constants

        Transform = Tree_transformer(self.variables, self.Readable(), Include_Constants)
        self.changed_tree = Transform.visit(self.tree)

    def clean(self):
        class AssignRemover(ast.NodeTransformer):
            def __init__(self, keep_vars):
                self.keep_vars = keep_vars

            def visit_Assign(self, node):
                if isinstance(node.targets[0], ast.Tuple):
                    keep = [i[0] for i in enumerate(node.targets[0].elts) if i[1].id in self.keep_vars] 
                    node.targets[0].elts = [node.targets[0].elts[i] for i in keep]
                    node.value.elts = [node.value.elts[i] for i in keep]
                    if len(node.targets[0].elts) == 1:
                        node.value = node.value.elts[0]
                        node.targets[0] = node.targets[0].elts[0]
                        return node
                    if len(node.targets[0].elts) > 0:
                        return node
                elif isinstance(node.targets[0], ast.Name) and node.targets[0].id in self.keep_vars:
                    return node

        used = set()
        
        for node in ast.walk(self.changed_tree):
            if isinstance(node, ast.Return):
                for name in ast.walk(node):
                    if isinstance(name, ast.Name):
                        used.add(name.id)
        #print(used)
        cleaner = AssignRemover(used)
        self.changed_tree = cleaner.visit(self.changed_tree)

    def __str__(self):
        return astunparse.unparse(self.changed_tree)

def add():
    a, a2 = 1.000*meter,2
    b, b1 = a, a2
    c = b*kilograms
    d = sqrt(c+2)
    return d


print(Tree_chopper(add, Readable = False))



