def calculateSteps(amount, units, syringeType, stepType):
    
    amount = amount
    units = units #can also be mililiters
    
    if "3" in syringeType == "3mL":
        dist = .555625 #distance bw .1 mL in cm 

    else:
        dist = .174625 #distance bw .1 mL in cm
    


    print("amount: ", amount)
    print("units: ", units)
    print("syringeType: ", syringeType)
    print("stepType: ", stepType)
    print("dist: ", dist)


    #catch for case of not thick or thin

    # --------- Calculation Note -----------
    # For threadsPerCm, there are 32 threads per inch,
    # and so I converted the 1 inch to cm and so I
    # multiplied the 32 x .393701 to get 12.598432
    threadsPerCm = 12.598432 #threads in 1 cm distance
    
    # Calculating the linear distance syringe should move 
    if units == "microliters":
        print("MICRO")
        multFactor = amount / 100 #the 100 is 100 microliters in .1 mL
        print("MULT FACTOR: ", multFactor)
        linDist = dist * multFactor #how much the syringe will linearly move in cm
                                   #for an amount in microLiters
    # else:
    #     #create code for mililiters
    #     multFactor = amount / .1 #amount mL div by .1 mL 
    #     linDist = dist * multFactor
   
    print("\n----------\nlinDist: {0}".format(linDist))

   # Calculating how many steps should take to travel linear distance
    threadsLinDist = threadsPerCm * linDist
    
    stepsTypeDict = {"Full":200,
                      "Half":400,
                      "1/4":800,
                      "1/8": 1600,
                      "1/16": 3200}
    stepsPerThread = stepsTypeDict[stepType] #steps per revolution, which is the same as thread
    finalSteps = round(stepsPerThread * threadsLinDist) # gets you steps to achieve the distance 
    return finalSteps

print(calculateSteps(5, "microliters", "3mL", "Half"))
