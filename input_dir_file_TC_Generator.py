import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
import json
import csv
import os
import webbrowser
from google import genai
from dotenv import load_dotenv
import logging
import re
import os
import subprocess
import sys

load_dotenv()

# Set up logging
logging.basicConfig(
    filename='demo_logs.log', 
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Gemini API Setup
client = genai.Client(api_key="AIzaSyAArgbFlCU5s1Gl3ElxIpp4zkJ3S0pIBR4")

# JSON output format template
json_output_template = {
    "tests": [
        {
            "testcase_title": "",
            "description": "",
            "sql": "",
            "expected_outcome": "",
            "recommendations": ""
        }
    ]
}

def read_file(file_path):
    try:
        if file_path.endswith('.csv'):
            return pd.read_csv(file_path)
        elif file_path.endswith('.xlsx'):
            return pd.read_excel(file_path, sheet_name=None)
        else:
            messagebox.showerror("Invalid File", "Please upload a CSV or Excel file.")
            return None
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")
        return None

def generate_prompt(sheet_name, file_data):
    prompt = f"""
Hi, Consider yourself an expertise with 20 years of experience of tester with a focus on designing test cases for big data migrations.
We need your expertise in writing test cases to thoroughly cover all the transformations applied in our migration process.

We have a source-to-target field mapping sheet along with transformation rules, and we need your help in writing all possible test cases to cover the transformation validations, along with SQL queries to perform the testing.    

We need the test case listing in the must in following JSON structure so we can generate a document out of the test cases and don't give any other text give only the json structure:

Desired response JSON structure: 
{json.dumps(json_output_template, indent=2)}

Here is the input JSON with source-to-target column mapping & transformation rules:
{json.dumps(file_data, indent=2)}

We look forward to your expert insights and test case recommendations to ensure comprehensive coverage for all transformation validations.
"""
    logging.info(f"Prompt for {sheet_name}:\n{prompt}")
    return prompt

def get_test_cases_from_gemini(prompt, sheet_name):
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        print(response.text)
        json_string = response.text.strip().replace('```json', '').replace('```', '')
        print(json_string)
        data = json.loads(json_string)
        return data.get("tests", [])

    except json.JSONDecodeError as e:
        messagebox.showerror("JSON Error", f"Error decoding JSON for {sheet_name}: {e}")
        logging.error(f"JSON Error for {sheet_name}: {e}")
        return []
    except Exception as e:
        messagebox.showerror("Error", f"{sheet_name}: {str(e)}")
        logging.error(f"Error processing {sheet_name}: {str(e)}")
        return []

def save_test_cases_to_csv(path, test_cases):
    fieldnames = list(test_cases[0].keys())
    with open(path, "w", newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(test_cases)

def get_next_output_folder(base_dir):
    output_path = os.path.join(base_dir, "input_dir_file_outputs")
    os.makedirs(output_path, exist_ok=True)

    existing = [
        int(match.group(1))
        for f in os.listdir(output_path)
        if os.path.isdir(os.path.join(output_path, f))
        and (match := re.match(r'^run_id_(\d+)$', f))
    ]
    next_num = max(existing, default=0) + 1
    return os.path.join(output_path, f"run_id_{next_num}")



def open_folder(folder_path):
    """
    Opens the specified folder using the default file explorer.
    """
    if sys.platform == "win32":
        subprocess.run(f'explorer "{folder_path}"')
    elif sys.platform == "darwin":
        subprocess.run(["open", folder_path])
    else:
        subprocess.run(["xdg-open", folder_path])

def process_directory():
    text_box.delete(1.0, tk.END)

    input_dir = filedialog.askdirectory(title="Select Input Directory with Excel Files")
    if not input_dir:
        return

    # Initial message
    text_box.insert(tk.END, "Thank you for your patience. We are currently generating test cases for the input files.\n\n")
    text_box.insert(tk.END, "logs:\n\n")
    text_box.update()

    combined_output_dir = get_next_output_folder(os.getcwd())
    os.makedirs(combined_output_dir, exist_ok=True)

    for filename in os.listdir(input_dir):
        if (filename.endswith(".xlsx") or filename.endswith(".csv")) and not filename.startswith("~$"):
            file_path = os.path.join(input_dir, filename)
            file_base = os.path.splitext(filename)[0]

            text_box.insert(tk.END, f"📁 Processing file: {filename}\n")
            text_box.update()

            try:
                file_data = read_file(file_path)
                if file_data is None:
                    continue

                combined_test_cases = []
                if isinstance(file_data, dict):
                    for sheet_name, sheet_df in file_data.items():
                        text_box.insert(tk.END, f"🔍 Generating test cases for sheet: {sheet_name}...\n")
                        text_box.update()

                        # Show "Processing..." and remember its position
                        processing_index = text_box.index(tk.END)
                        text_box.insert(tk.END, "🔄 Processing... Please wait...\n")
                        text_box.update()

                        # Generate test cases
                        sheet_json_data = sheet_df.to_dict(orient='records')
                        prompt = generate_prompt(sheet_name, sheet_json_data)
                        test_cases = get_test_cases_from_gemini(prompt, sheet_name)

                        # Once test cases are generated, remove the "Processing..." line
                        line_number = processing_index.split('.')[0]
                        start_index = f"{line_number}.0"
                        end_index = f"{line_number}.end"
                        text_box.delete(start_index, end_index)  # Deletes the "Processing..." line
                        text_box.update()

                        if test_cases:
                            combined_test_cases.extend(test_cases)
                elif isinstance(file_data, pd.DataFrame):  # .csv
                    sheet_name = file_base
                    sheet_json_data = file_data.to_dict(orient='records')
                    prompt = generate_prompt(sheet_name, sheet_json_data)
                    test_cases = get_test_cases_from_gemini(prompt, sheet_name)
                    if test_cases:
                        combined_test_cases.extend(test_cases)
                if combined_test_cases:
                    output_csv = os.path.join(combined_output_dir, f"{file_base}_test_cases.csv")
                    save_test_cases_to_csv(output_csv, combined_test_cases)
                    text_box.insert(tk.END, f"✅ Saved test cases to {output_csv}\n")
                else:
                    text_box.insert(tk.END, f"⚠️ No test cases found in {filename}\n")

                text_box.update()

            except Exception as e:
                text_box.insert(tk.END, f"❌ Error processing {filename}: {str(e)}\n")
                logging.error(f"Error processing {filename}: {str(e)}")
                text_box.update()

    # Completion message
    text_box.insert(tk.END, f"\n✅ All Excel files processed.\n")
    text_box.insert(tk.END, f"\n📂 Output Directory: {combined_output_dir}\n")
    text_box.yview(tk.END)
    text_box.update()

    # Clickable link to output folder
    link_label.config(text=f"📁 Open Output Folder: {combined_output_dir}", fg="blue", cursor="hand2")
    link_label.bind("<Button-1>", lambda e: open_folder(combined_output_dir))

# GUI Setup
window = tk.Tk()
window.title("Test Case Generator")
window.geometry("750x600")

process_button = tk.Button(window, text="📂 Select Input Directory", command=process_directory)
process_button.pack(pady=10)

# log_label = tk.Label(window, text="Logs:", font=("Arial", 11, "bold"))
# log_label.pack()

text_box = tk.Text(window, wrap=tk.WORD, width=95, height=25)
text_box.pack(padx=10, pady=5)

scrollbar = tk.Scrollbar(window, command=text_box.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
text_box.config(yscrollcommand=scrollbar.set)

link_label = tk.Label(window, text="", fg="blue", cursor="hand2", font=("Arial", 10, "bold"))
link_label.pack(pady=10)

window.mainloop()
