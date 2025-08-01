import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
import json
import csv
import os
from google import genai
from dotenv import load_dotenv
import time
import logging


load_dotenv()

# Set up logging
logging.basicConfig(
    filename='demo_logs.log', 
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Gemini API Setup
client = genai.Client(api_key=os.getenv("api_key"))  

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

# Shared output CSV path
directory = "main_outputs"
if not os.path.exists(directory):
    os.makedirs(directory)
FINAL_CSV_PATH = os.path.join(os.getcwd(), directory, f"test_cases_output_{int(time.time())}.csv")
logging.info(f"output file name: {FINAL_CSV_PATH}")

# Read file (CSV or Excel)
def read_file(file_path):
    if file_path.endswith('.csv'):
        return pd.read_csv(file_path)
    elif file_path.endswith('.xlsx'):
        return pd.read_excel(file_path, sheet_name=None)
    else:
        messagebox.showerror("Invalid File", "Please upload a CSV or Excel file.")
        return None

# Prompt generator
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
    logging.info(f"--------------------------------------------------------------------")
    logging.info(f"prompt: {prompt}")
    return prompt

# Gemini API handler
def process_prompt_and_append_to_csv(prompt, sheet_name, is_first=False):
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )

        json_string = response.text.strip('
').replace('json', '')
        data = json.loads(json_string)
        test_cases = data.get('tests', [])

        if not test_cases:
            messagebox.showwarning("No Test Cases", f"No 'tests' found in the JSON data for {sheet_name}.")
            return

        fieldnames = list(test_cases[0].keys())

        # Append mode, write header only for first write
        with open(FINAL_CSV_PATH, "a", newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)

            if is_first or not os.path.exists(FINAL_CSV_PATH) or os.path.getsize(FINAL_CSV_PATH) == 0:
                writer.writeheader()
                
            writer.writerow({
                fieldnames[0]: f"📄 Table Name: {sheet_name}"
            })
            writer.writerows(test_cases)
            writer.writerow({})  # Blank line between table outputs

    except json.JSONDecodeError as e:
        messagebox.showerror("JSON Error", f"Error decoding JSON for {sheet_name}: {e}")
        logging.error("JSON Error", f"Error decoding JSON for {sheet_name}: {e}")
    except Exception as e:
        messagebox.showerror("Error", f"{sheet_name}: {str(e)}")
        logging.error("Error", f"{sheet_name}: {str(e)}")

# File upload handler
def upload_file():
    text_box.delete(1.0, tk.END)

    file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv"), ("Excel Files", "*.xlsx")])
    if not file_path:
        return

    # # Clear output file if exists
    # if os.path.exists(FINAL_CSV_PATH):
    #     os.remove(FINAL_CSV_PATH)

    file_data = read_file(file_path)
    if file_data is None:
        return

    is_first = True

    if isinstance(file_data, dict):  # Excel with multiple sheets
        for sheet_name, sheet_df in file_data.items():
            sheet_json_data = sheet_df.to_dict(orient='records')
            prompt = generate_prompt(sheet_name, sheet_json_data)
            text_box.insert(tk.END, f"Generating test cases for sheet: {sheet_name}...\n")
            process_prompt_and_append_to_csv(prompt, sheet_name, is_first)
            is_first = False
    elif isinstance(file_data, pd.DataFrame):  # CSV file
        if 'Table Name' in file_data.columns:
            for table_name, group_df in file_data.groupby('Table Name'):
                prompt = generate_prompt(table_name, group_df.to_dict(orient='records'))
                text_box.insert(tk.END, f"Generating test cases for table: {table_name}...\n")
                process_prompt_and_append_to_csv(prompt, table_name, is_first)
                is_first = False
        else:
            prompt = generate_prompt("Sheet1", file_data.to_dict(orient='records'))
            text_box.insert(tk.END, "Generating test cases for CSV file...\n")
            process_prompt_and_append_to_csv(prompt, "Sheet1", is_first)

    text_box.insert(tk.END, f"✅ All test cases saved to:\n{FINAL_CSV_PATH}\n")
    text_box.yview(tk.END)

# GUI Setup
window = tk.Tk()
window.title("Test Case Generator")
window.geometry("700x500")

upload_button = tk.Button(window, text="Upload CSV/Excel File", command=upload_file)
upload_button.pack(pady=20)

text_box = tk.Text(window, wrap=tk.WORD, width=85, height=20)
text_box.pack(padx=10, pady=10)

scrollbar = tk.Scrollbar(window, command=text_box.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
text_box.config(yscrollcommand=scrollbar.set)

window.mainloop()