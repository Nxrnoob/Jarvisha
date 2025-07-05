import re
import json
import os

def parse_students_txt(content):
    students = []
    # Split content by "Student" followed by a number and a colon
    student_blocks = re.split(r'Student \d+:\s*\n', content.strip())

    for block in student_blocks:
        if not block.strip():
            continue

        student_data = {}
        # Use a general approach to find all key-value pairs
        # This is more flexible than a strict regex for each field
        lines = block.strip().split('\n')
        
        # A variable to hold multi-line text, e.g. for remarks
        current_key = None
        
        for line in lines:
            match = re.match(r'([^:]+):\s*(.*)', line)
            if match:
                key, value = match.groups()
                key_clean = key.strip().lower().replace(' ', '_')
                
                # Handle special case for multi-line marks under "Marks:"
                if key_clean == 'marks' and not value:
                    student_data[key_clean] = {}
                    current_key = 'marks'
                elif key_clean == 'remarks' and value:
                     student_data[key_clean] = value
                     current_key = 'remarks'
                elif value:
                    student_data[key_clean] = value.strip()
                    current_key = None # reset key
            
            # Handle marks items (e.g., "- Mathematics: 94")
            elif line.strip().startswith('-') and 'marks' in student_data:
                mark_match = re.match(r'\s*-\s*([^:]+):\s*(\d+)', line)
                if mark_match:
                    subject, score = mark_match.groups()
                    student_data['marks'][subject.strip()] = int(score)
            
            # Append to remarks if it's a continuation line
            elif current_key == 'remarks' and line.strip():
                student_data['remarks'] += ' ' + line.strip()

        # Standardize keys
        if 'roll_number' in student_data:
            student_data['roll_no'] = student_data.pop('roll_number')
        if 'performance_summary' in student_data:
            student_data['remarks'] = student_data.pop('performance_summary')

        if student_data:
            students.append(student_data)
            
    return students

def parse_professors_txt(content):
    professors = []
    professor_blocks = re.split(r'Professor \d+:\n', content.strip())

    for block in professor_blocks:
        if not block.strip():
            continue
        
        professor_data = {}
        lines = block.strip().split('\n')
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key_clean = key.strip().lower().replace(' ', '_')
                professor_data[key_clean] = value.strip()
        professors.append(professor_data)
        
    return professors


def main():
    # Define paths
    student_txt_path = os.path.join('backend', 'student.txt')
    professor_txt_path = os.path.join('backend', 'professor.txt')
    
    output_dir = os.path.join('backend', 'data')
    os.makedirs(output_dir, exist_ok=True)
    
    student_json_path = os.path.join(output_dir, 'students.json')
    professor_json_path = os.path.join(output_dir, 'professors.json')

    # Process students
    with open(student_txt_path, 'r') as f:
        student_content = f.read()
    students_data = parse_students_txt(student_content)
    with open(student_json_path, 'w') as f:
        json.dump(students_data, f, indent=2)
    print(f"Successfully converted {len(students_data)} student records to {student_json_path}")

    # Process professors
    with open(professor_txt_path, 'r') as f:
        professor_content = f.read()
    professors_data = parse_professors_txt(professor_content)
    with open(professor_json_path, 'w') as f:
        json.dump(professors_data, f, indent=2)
    print(f"Successfully converted {len(professors_data)} professor records to {professor_json_path}")


if __name__ == '__main__':
    main() 