import subprocess

input_data = "3\n01011101\n1\n10\n20\n0.5\n100"

result = subprocess.run(["python", "process.py"], input=input_data, capture_output=True, text=True)
print(result.stdout)
