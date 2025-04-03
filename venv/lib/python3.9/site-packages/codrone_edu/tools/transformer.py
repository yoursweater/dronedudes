import ast
import astor

non_await_drone_functions = [
    "convert_meter", "convert_millimeter",
    "get_left_joystick_y", "get_left_joystick_x",
    "get_right_joystick_y", "get_right_joystick_x",
    "get_button_data", "l1_pressed", "l2_pressed",
    "r1_pressed", "r2_pressed", "h_pressed",
    "power_pressed", "up_arrow_pressed", "left_arrow_pressed",
    "right_arrow_pressed", "down_arrow_pressed", "s_pressed", "p_pressed",
    "set_roll", "set_pitch", "set_yaw", "set_throttle",
    "print_move_values", "percent_error", "get_move_values",
    "predict_colors", "load_classifier", "print_num_data", "append_color_data", "new_color_data",
    "detect_colors", "load_color_data",
    "reset_classifier"
]

class FunctionCollector(ast.NodeVisitor):
    def __init__(self):
        self.custom_functions = set()

    def visit_FunctionDef(self, node):
        self.custom_functions.add(node.name)
        self.generic_visit(node)

class DroneInstanceFinder(ast.NodeVisitor):
    def __init__(self):
        self.drone_instance_name = None

    def visit_Assign(self, node):
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
            if node.value.func.id == 'Drone':
                if node.targets[0].id != 'drone':
                    raise ValueError(f"Drone instance must be named 'drone', found '{node.targets[0].id}' instead.")
                self.drone_instance_name = node.targets[0].id

class AsyncTransformer(ast.NodeTransformer):
    def __init__(self, custom_functions, drone_instance_name):
        self.custom_functions = custom_functions
        self.drone_instance_name = drone_instance_name

    def copy_location(self, new_node, old_node):
        ast.copy_location(new_node, old_node)
        if hasattr(old_node, 'end_lineno'):
            new_node.end_lineno = old_node.end_lineno
        if hasattr(old_node, 'end_col_offset'):
            new_node.end_col_offset = old_node.end_col_offset
        return new_node
    
    def visit_Assign(self, node):
        # Detect assignments like drone = Drone() and comment them out
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
            if node.value.func.id == 'Drone' and isinstance(node.targets[0], ast.Name):
                comment_text = f'{node.targets[0].id} = {node.value.func.id}()'
                comment_node = ast.Expr(value=ast.Constant(value=f'# {comment_text}'))
                return self.copy_location(comment_node, node)
        return self.generic_visit(node)

    def visit_Module(self, node):
        # Separate import statements from other code
        imports = [n for n in node.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        other_statements = [n for n in node.body if not isinstance(n, (ast.Import, ast.ImportFrom))]

        # Remove extra newlines in other_statements
        other_statements = [stmt for stmt in other_statements if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value == '')]

        # Insert drone.reset_classifier() at the beginning
        reset_classifier_call = ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id=self.drone_instance_name, ctx=ast.Load()),
                    attr="reset_classifier",
                    ctx=ast.Load(),
                ),
                args=[],
                keywords=[],
            )
        )
        other_statements.insert(0, reset_classifier_call)

        # Wrap the rest of the code in _wrapper function
        wrapper_function = ast.AsyncFunctionDef(
            name='_wrapper',
            args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
            body=other_statements,
            decorator_list=[]
        )

        node.body = imports + [wrapper_function]
        self.generic_visit(wrapper_function)  # Visit the wrapped code inside _wrapper
        return node
    
    def visit_FunctionDef(self, node):
        new_node = ast.AsyncFunctionDef(
            name=node.name,
            args=node.args,
            body=node.body,
            decorator_list=node.decorator_list,
            returns=node.returns
        )
        new_node = self.copy_location(new_node, node)
        self.generic_visit(new_node)
        return new_node
    
    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == self.drone_instance_name:
            # If the function is pair(), open(), disconnect() or close(), replace with dummy_function()
            if node.func.attr in ['pair', 'open', 'connect', 'disconnect', 'close']:
                # Replace the original call with a call to drone.dummy_function()
                new_node = ast.Call(
                    func=ast.Attribute(value=ast.Name(id=self.drone_instance_name, ctx=ast.Load()), attr='dummy_function', ctx=ast.Load()),
                    args=[], keywords=[]
                )
                return self.copy_location(new_node, node)
            elif node.func.attr not in non_await_drone_functions:
                new_node = ast.Await(value=node)
                return self.copy_location(new_node, node)
        elif isinstance(node.func, ast.Name) and node.func.id in self.custom_functions:
            new_node = ast.Await(value=node)
            return self.copy_location(new_node, node)
        elif isinstance(node.func, ast.Name) and node.func.id == 'input':
            new_node = ast.Await(value=node)
            return self.copy_location(new_node, node)
        return self.generic_visit(node)

class SleepTransformer(ast.NodeTransformer):
    def copy_location(self, new_node, old_node):
        ast.copy_location(new_node, old_node)
        if hasattr(old_node, 'end_lineno'):
            new_node.end_lineno = old_node.end_lineno
        if hasattr(old_node, 'end_col_offset'):
            new_node.end_col_offset = old_node.end_col_offset
        return new_node
    
    def visit_Import(self, node):
        for alias in node.names:
            if alias.name == 'time':
                alias.name = 'asyncio'
        return node

    def visit_ImportFrom(self, node):
        if node.module == 'time':
            node.module = 'asyncio'
        return node

    def visit_Call(self, node):
        # Convert time.sleep calls to await asyncio.sleep
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            if node.func.value.id == 'time' and node.func.attr == 'sleep':
                node.func.value.id = 'asyncio'
                new_node = ast.Await(value=node)
                return self.copy_location(new_node, node)
        return self.generic_visit(node)

class CheckInterruptTransformer(ast.NodeTransformer):    
    def copy_location(self, new_node, old_node):
        ast.copy_location(new_node, old_node)
        if hasattr(old_node, 'end_lineno'):
            new_node.end_lineno = old_node.end_lineno
        if hasattr(old_node, 'end_col_offset'):
            new_node.end_col_offset = old_node.end_col_offset
        return new_node
    
    def generic_visit(self, node):
        if isinstance(node, ast.stmt) and not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.If, ast.For, ast.While, ast.Try)):
            check_interrupt_call = ast.Expr(value=ast.Call(
                func=ast.Name(id='checkInterrupt', ctx=ast.Load()),
                args=[], keywords=[]
            ))
            check_interrupt_call = self.copy_location(check_interrupt_call, node)
            return [node, check_interrupt_call]
        return super().generic_visit(node)

def transform_code(code):
    # Parse the code into an AST
    tree = ast.parse(code)

    function_collector = FunctionCollector()
    function_collector.visit(tree)

    drone_finder = DroneInstanceFinder()
    drone_finder.visit(tree)

    # Transform the AST
    async_transformer = AsyncTransformer(function_collector.custom_functions, "drone")
    sleep_transformer = SleepTransformer()
    check_interrupt_transformer = CheckInterruptTransformer()

    tree = async_transformer.visit(tree)
    tree = sleep_transformer.visit(tree)
    tree = check_interrupt_transformer.visit(tree)

    # Ensure the tree is correctly fixed
    ast.fix_missing_locations(tree)

    # Convert the modified AST back to code
    # modified_code = ast.unparse(tree)
    modified_code = astor.to_source(tree)
    return tree, modified_code


# test="""
# dataset = "color_data"
# colors = ["green", "red", "blue", "yellow"]
# for color in colors:
#     data = []
#     samples = 500
#     for i in range(1):
#         print("Sample: ", i+1)
#         next = input("Press enter to calibrate " + color)
#         print("0% ", end="")
#         for j in range(samples):
#             color_data = drone.get_color_data()[0:9]
#             data.append(color_data)
#             time.sleep(0.005)
#             if j % 10 == 0:
#                 print("-", end="")
#         print(" 100%")
#     drone.new_color_data(color, data, dataset)
# print("Done calibrating.")
# """

# transformed_ast, transformed_code = transform_code(test)
# print(transformed_code)

# code_object = compile(transformed_ast, filename="<ast>", mode="exec")
# print(code_object)
# print(transformed_ast)