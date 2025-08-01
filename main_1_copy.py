import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
import json
import csv
import os
import time
import logging
import re
import subprocess
import sys
from google import genai
from dotenv import load_dotenv

load_dotenv()

# Logging Setup
logging.basicConfig(
    filename='demo_logs.log', 
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Gemini Setup
client = genai.Client(api_key=os.getenv("api_key"))

# JSON output format
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
Hi, Consider yourself an expert tester with a focus on designing test cases for big data migrations.
We need your expertise in writing test cases to thoroughly cover all the transformations applied in our migration process.

We have a source-to-target field mapping sheet along with transformation rules, and we need your help in writing all possible test cases to cover the transformation validations, along with SQL queries to perform the testing.    

We need the test case listing in the following JSON structure so we can generate a document out of the test cases:

Desired response JSON structure: 
{json.dumps(json_output_template, indent=2)}

Here is the input JSON with source-to-target column mapping & transformation rules:
{json.dumps(file_data, indent=2)}

Please add maximum test cases to cover complex transformations.

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

        json_string = response.text.strip().replace('```json', '').replace('```', '')
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

def save_test_cases_to_csv(path, test_cases, sheet_name, is_first=False):
    fieldnames = list(test_cases[0].keys())

    with open(path, "a", newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        
        if is_first or os.path.getsize(path) == 0:
            writer.writeheader()

        writer.writerow({
            fieldnames[0]: f"📄 Table Name: {sheet_name}"
        })
        writer.writerows(test_cases)
        writer.writerow({})  # Spacer row

def get_next_output_folder(base_dir):
    output_path = os.path.join(base_dir, "main_outputs")
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
    if sys.platform == "win32":
        subprocess.run(f'explorer "{folder_path}"')
    elif sys.platform == "darwin":
        subprocess.run(["open", folder_path])
    else:
        subprocess.run(["xdg-open", folder_path])

def upload_file():
    text_box.delete(1.0, tk.END)

    file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv"), ("Excel Files", "*.xlsx")])
    if not file_path:
        return

    output_dir = get_next_output_folder(os.getcwd())
    os.makedirs(output_dir, exist_ok=True)
    final_csv_path = os.path.join(output_dir, f"test_cases_output.csv")

    file_data = read_file(file_path)
    if file_data is None:
        return

    text_box.insert(tk.END, "Generating test cases for selected file...\n\n")
    text_box.insert(tk.END, "logs:\n\n")
    text_box.update()

    is_first = True

    if isinstance(file_data, dict):  # Excel with multiple sheets
        for sheet_name, sheet_df in file_data.items():
            text_box.insert(tk.END, f"🔍 Generating test cases for sheet: {sheet_name}...\n")
            text_box.update()

            processing_index = text_box.index(tk.END)
            text_box.insert(tk.END, "🔄 Processing... Please wait...\n")
            text_box.update()

            prompt = generate_prompt(sheet_name, sheet_df.to_dict(orient='records'))
            test_cases = get_test_cases_from_gemini(prompt, sheet_name)

            # Remove "Processing..." line
            line_number = processing_index.split('.')[0]
            start_index = f"{line_number}.0"
            end_index = f"{line_number}.end"
            text_box.delete(start_index, end_index)
            text_box.update()

            if test_cases:
                save_test_cases_to_csv(final_csv_path, test_cases, sheet_name, is_first)
                text_box.insert(tk.END, f"✅ Test cases saved for {sheet_name}\n")
                is_first = False
            else:
                text_box.insert(tk.END, f"⚠️ No test cases generated for {sheet_name}\n")

            text_box.update()

    elif isinstance(file_data, pd.DataFrame):  # Single sheet (CSV)
        sheet_name = os.path.basename(file_path).split('.')[0]
        text_box.insert(tk.END, f"🔍 Generating test cases for: {sheet_name}...\n")

        prompt = generate_prompt(sheet_name, file_data.to_dict(orient='records'))
        test_cases = get_test_cases_from_gemini(prompt, sheet_name)

        if test_cases:
            save_test_cases_to_csv(final_csv_path, test_cases, sheet_name, is_first)
            text_box.insert(tk.END, f"✅ Test cases saved for {sheet_name}\n")
        else:
            text_box.insert(tk.END, f"⚠️ No test cases generated for {sheet_name}\n")

        text_box.update()

    text_box.insert(tk.END, "\n✅ File processing complete.\n")
    text_box.insert(tk.END, f"\n📂 Output Directory: {output_dir}\n")
    text_box.yview(tk.END)

    link_label.config(text=f"📁 Open Output Folder: {output_dir}", fg="blue", cursor="hand2")
    link_label.bind("<Button-1>", lambda e: open_folder(output_dir))

# GUI Setup
window = tk.Tk()
window.title("Test Case Generator")
window.geometry("750x600")

upload_button = tk.Button(window, text="📁 Select Single File", command=upload_file)
upload_button.pack(pady=10)

text_box = tk.Text(window, wrap=tk.WORD, width=95, height=25)
text_box.pack(padx=10, pady=5)

scrollbar = tk.Scrollbar(window, command=text_box.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
text_box.config(yscrollcommand=scrollbar.set)

link_label = tk.Label(window, text="", fg="blue", cursor="hand2", font=("Arial", 10, "bold"))
link_label.pack(pady=10)

window.mainloop()
