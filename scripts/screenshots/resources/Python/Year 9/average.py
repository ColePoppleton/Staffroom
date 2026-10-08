# FAKE DATA: invented program for screenshots (same as examples/year9.py)
# Average of five test scores
scores = [45, 62, 58, 71, 39]
total = 0
count = 0
for score in scores:
    total = total + score
    count = count + 1
average = total / count
if average >= 50:
    print("Well done")
else:
    print("Keep going")
print("Average:", average)
