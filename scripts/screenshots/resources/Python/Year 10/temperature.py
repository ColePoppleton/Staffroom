# FAKE DATA: invented program for screenshots; it reads input() so the
# trace tool can show what happens when the Inputs box is left empty.
celsius = int(input("Temperature in Celsius: "))
fahrenheit = celsius * 9 / 5 + 32
if fahrenheit > 86:
    print("Hot")
else:
    print("Not hot")
print(celsius, "C is", fahrenheit, "F")
