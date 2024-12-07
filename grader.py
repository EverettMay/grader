import os
import sys
import importlib.util
import shutil
from io import StringIO
import contextlib
import traceback
import glob
import builtins
import time
import signal
import threading

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Program execution timed out")

def load_input_prompts():
    """Load input prompts from input.txt"""
    with open('input.txt', 'r') as f:
        return [line.strip() for line in f.readlines()]

def import_student_module(file_path):
    """Dynamically import a Python file"""
    spec = importlib.util.spec_from_file_location("student_module", file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["student_module"] = module
    spec.loader.exec_module(module)
    return module

def create_project_folder(project_name):
    """Create a folder for the project if it doesn't exist"""
    folder_name = project_name.replace('.py', '')
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    return folder_name

def run_with_timeout(func, args=(), timeout_duration=10):
    """Run a function with a timeout"""
    result = []
    error = []

    def target():
        try:
            result.append(func(*args))
        except Exception as e:
            error.append(str(e))
            error.append(traceback.format_exc())

    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout_duration)

    if thread.is_alive():
        return None, ["Program execution timed out after {} seconds".format(timeout_duration)]
    
    if error:
        return None, error
        
    return result[0] if result else None, None

def capture_output_and_files(module, input_prompts, folder_name):
    """Capture stdout and handle inputs while running the main function"""
    captured_lines = []
    input_idx = 0
    stdout_buffer = StringIO()
    
    # Get initial state of txt files
    initial_txt_files = set(f for f in os.listdir('.') if f.endswith('.txt'))
    
    def mock_input(prompt=''):
        nonlocal input_idx
        
        # Flush any pending output from stdout_buffer
        stdout_content = stdout_buffer.getvalue()
        if stdout_content:
            captured_lines.extend(stdout_content.splitlines())
            stdout_buffer.seek(0)
            stdout_buffer.truncate()
            
        if prompt:
            captured_lines.append(prompt.rstrip())
        
        if input_idx < len(input_prompts):
            value = input_prompts[input_idx]
            captured_lines.append(value)
            input_idx += 1
            return value
        return '9'
    
    original_input = builtins.input
    builtins.input = mock_input
    
    try:
        with contextlib.redirect_stdout(stdout_buffer):
            if hasattr(module, 'main'):
                # Run the main function with timeout
                _, error = run_with_timeout(module.main)
                if error:
                    captured_lines.extend(error)
            else:
                captured_lines.append("Error: No main() function found in student's code")
            
            # Capture any remaining output
            final_output = stdout_buffer.getvalue()
            if final_output:
                captured_lines.extend(final_output.splitlines())
    
    except Exception as e:
        captured_lines.append(f"Error occurred: {str(e)}")
        captured_lines.append(traceback.format_exc())
    finally:
        builtins.input = original_input
        
        # Handle file operations even if there was an error
        try:
            # Give time for any file operations to complete
            time.sleep(1)
            
            # Find new txt files
            current_txt_files = set(f for f in os.listdir('.') if f.endswith('.txt'))
            new_txt_files = current_txt_files - initial_txt_files - {'input.txt'}
            
            # Move new txt files to project folder
            for txt_file in new_txt_files:
                try:
                    if os.path.exists(txt_file):
                        shutil.move(txt_file, os.path.join(folder_name, txt_file))
                except Exception as e:
                    captured_lines.append(f"Error moving {txt_file}: {str(e)}")
        except Exception as e:
            captured_lines.append(f"Error handling files: {str(e)}")
    
    return captured_lines

def process_project(project_file):
    """Process a single project file"""
    try:
        # Create project folder
        folder_name = create_project_folder(project_file)
        
        # Import student's module
        module = import_student_module(project_file)
        
        # Load input prompts
        input_prompts = load_input_prompts()
        
        # Run the project, capture output and handle file movements
        output = capture_output_and_files(module, input_prompts, folder_name)
        
        # Write output to file
        output_path = os.path.join(folder_name, 'output.txt')
        with open(output_path, 'w') as f:
            f.write('\n'.join(output))
        
        # Move project file to its folder after processing
        if os.path.exists(project_file):
            shutil.move(project_file, os.path.join(folder_name, project_file))
        
        print(f"Successfully processed {project_file}")
        
    except Exception as e:
        print(f"Failed to process {project_file}: {str(e)}")
        traceback.print_exc()
        
        # Even if processing failed, try to create output file with error message
        try:
            if not os.path.exists(folder_name):
                os.makedirs(folder_name)
            output_path = os.path.join(folder_name, 'output.txt')
            with open(output_path, 'w') as f:
                f.write(f"Error processing project: {str(e)}\n")
                f.write(traceback.format_exc())
            
            # Try to move the project file if it exists
            if os.path.exists(project_file):
                shutil.move(project_file, os.path.join(folder_name, project_file))
        except Exception as move_error:
            print(f"Failed to handle error case: {str(move_error)}")

def main():
    """Main function to process all Python files in the current directory"""
    python_files = [f for f in os.listdir('.') if f.endswith('.py') and f != 'grader.py']
    print(f"Found {len(python_files)} Python files to process")
    
    for project_file in python_files:
        print(f"\nProcessing {project_file}...")
        process_project(project_file)
        print(f"Completed processing {project_file}")

if __name__ == "__main__":
    main()
