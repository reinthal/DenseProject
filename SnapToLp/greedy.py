from lib import snap
import sys
import time
import snapGraphCopy

# Consider every argument after the first (which is the name of the executed
# command) to be a graph file. Load them all and store them in a list.
def loadGraphs():
    Graphs = []
    for arg in sys.argv[1:]:
        Graphs.append(snap.LoadEdgeList(snap.PUNGraph, arg, 0, 1))
        sys.stdout.write("Imported " + arg + ": ")
        printQuickStats(Graphs[len(Graphs)-1])
    return Graphs

def preprocess(Graphs):
    ##### preprocessing start #####
    # TODO: clean up the preprocessing, possibly make it into a new function

    v = []

    # appends node set for all graphs to v.
    for g in range(0,len(Graphs)):
        a = []
        for n in Graphs[g].Nodes():
            a.append(n.GetId())
        v.append(set(a))

    # take the intersection, giving us all common nodes.
    u = list(set.intersection(*v))

    # converts to a snap-vector
    w = snap.TIntV()
    for i in u:
        w.Add(i)

    # update graph list with subgraph induced by common nodes.
    for g in Graphs:
        subGraph(g, u)

# TODO: Use snap.GetSubGraph() instead? It returned some sort of NoneType object
# when I tried. It gave the following error when calling GetNodes on the
# returned graph.
# AttributeError: 'NoneType' object has no attribute 'GetNodes'

    ##### preprocessing end #####

# Make g into an induced subgraph of g, removing all nodes that are not in v.
# Keep the list of nodes to remove in a list to avoid removing while iterating
# over the graph.
# This function is used because the one in snap would not work.
def subGraph(g, v):
    nodesToRemove = []
    for n in g.Nodes():
        if not n.GetId() in v:
            nodesToRemove.append(n.GetId())
    for n in nodesToRemove:
        g.DelNode(n)

# Find the node with the smallest degree.
def findSmallestDegree(graphs):
    global lookupTable
    degree = 0
    while len(lookupTable[degree]) == 0:
        degree += 1
    smallestNode = lookupTable[degree][0]
    assert graphs[0].IsNode(smallestNode)
    return smallestNode

# Create the data structure that is used in the function findSmallestDegree().
# It is a list-of-lists, such that lookupTable[1] is a list of all nodes of
# degree 1 (as reported by getMinDegree()).
def initLookupTable(graphs):
    global lookupTable
    lookupTable = []
    for n in graphs[0].Nodes():
        addToLookupTable(graphs, n.GetId())

def addToLookupTable(graphs, node):
    global lookupTable
    degree = getMinDegree(graphs, node)
    while degree >= len(lookupTable):
        lookupTable.append([])
    lookupTable[degree].append(node)
    #print("Added " + str(node))
    #printLookupTable()

def removeFromLookupTable(graphs, node):
    global lookupTable
    degree = getMinDegree(graphs, node)
    if lookupTable[degree].count(node) > 0:
        lookupTable[degree].remove(node)
    #print("Removed " + str(node))
    #printLookupTable()

# For debugging.
def printLookupTable():
    global lookupTable
    deg = 0
    for degreeList in lookupTable:
        sys.stdout.write(str(deg) + ": ")
        for node in degreeList:
            sys.stdout.write(str(node) + " ")
        print("")
        deg += 1

# Get the smallest degree of node, in all graphs.
def getMinDegree(graphs, node):
    result = float("Infinity")
    for g in graphs:
        assert g.IsNode(node)
        result = min(result, g.GetNI(node).GetDeg())
    return result

# Calculate the average degree as density of a single graph.
def density(g):
    # Avoid division by zero.
    if g.GetNodes() == 0:
        return 0
    else:
        return g.GetEdges()/float(g.GetNodes())

# The density of a set of graphs is the minimum density among them.
def densityMultiple(graphs):
    result = float("Infinity")
    for g in graphs:
        result = min(result, density(g))
    return result

# Print progress bar based on size of the graph (it is reduced to zero nodes).
def printProgress(message, originalSize, currentSize):
    global lastUpdateTimeStamp
    updateFrequency = 10 # Update progress every X seconds.
    try:
        if time.clock() - lastUpdateTimeStamp < updateFrequency:
            return
    except NameError:
        lastUpdateTimeStamp = time.clock()
    lastUpdateTimeStamp = time.clock()
    percentage = '%.0f' % (100*(originalSize-currentSize)/(1.0*originalSize))
    print(message + percentage + "% done")

# Get the densest common subgraph using the greedy algorithm.
def getDCS_Greedy(originalGraphs):
    # Don't touch any of the original graphs, caller may use them further.
    graphs = []
    for og in originalGraphs:
        graphs.append(snapGraphCopy.copyGraph(og))
    # To avoid having to do two full passes over the entire graph, we keep
    # track of a set of nodes that we know contains the densest subgraph. The
    # trick is to make it as small as possible while also minimizing the number
    # of updates.
    searchSpace = []
    for n in graphs[0].Nodes():
        searchSpace.append(n.GetId())
    # Create a table of nodes by degree, to enable faster lookup.
    initLookupTable(graphs)

    # Pass 1, to find the subgraph with the highest density.
    highestDensity = 0
    updatesSinceSave = 0
    while graphs[0].GetNodes() > 1:
        printProgress("Searching for highest density: ",
                originalGraphs[0].GetNodes(), graphs[0].GetNodes())
        if densityMultiple(graphs) > highestDensity:
            highestDensity = densityMultiple(graphs)
            updatesSinceSave += 1
            if updatesSinceSave >= 100:
                updatesSinceSave = 0
                searchSpace = []
                for n in graphs[0].Nodes():
                    searchSpace.append(n.GetId())
        removeSmallestDegreeNode(graphs)

    print("Highest density found: " + str(highestDensity))

    # Pass 2, look for the subgraph that has a density equal to highest seen.
    # Since we start from a much smaller search space, this can be very fast.
    print("Going back to find best solution. Search space is " +
            str(len(searchSpace)) + " nodes")
    graphs = []
    for og in originalGraphs:
        graphs.append(snapGraphCopy.copyGraph(og))
    for g in graphs:
        subGraph(g, searchSpace)
    initLookupTable(graphs)

    while graphs[0].GetNodes() > 1:
        # Is there a chance of some rounding error here? Comparing floats
        # without a margin of error. But they come from the same division.
        if densityMultiple(graphs) >= highestDensity:
            break
        removeSmallestDegreeNode(graphs)

    # TODO: which edges should be in the returned graph? Should we return the
    # full graph set?
    return (graphs[0], highestDensity)

# Find the node with the smallest degree and remove it. Also update the lookup
# table. Not only the removed node needs to be updated, also all nodes sharing
# an edge with it.
def removeSmallestDegreeNode(graphs):
    smallestNode = findSmallestDegree(graphs)
    neighbors = getNeighbors(graphs, smallestNode)
    removeFromLookupTable(graphs, smallestNode)
    for n in neighbors:
        removeFromLookupTable(graphs, n)
    for g in graphs:
        g.DelNode(smallestNode)
    for n in neighbors:
        addToLookupTable(graphs, n)

# Return a list of all nodes connected to node, in any of the graphs.
def getNeighbors(graphs, node):
    neighbors = []
    for g in graphs:
        assert g.IsNode(node)
        degree = g.GetNI(node).GetDeg()
        for edgeNum in range(0, degree):
            neighbor = g.GetNI(node).GetNbrNId(edgeNum)
            if not neighbor in neighbors:
                neighbors.append(neighbor)
    #sys.stdout.write(str(node) + " neighbors ")
    #print(neighbors)
    return neighbors

def printQuickStats(g):
    print(str(g.GetNodes()) + " nodes and " + str(g.GetEdges()) + " edges.")

# A function to measure how long something takes to run.
# Returns a string holding the time since last time the function was called.
# Uses a global variable to hold the time of previous call.
def timer():
    global lastTimeStamp
    try:
        elapsedTime = time.clock() - lastTimeStamp
    except NameError:
        # First time the function is called there is no startTime declared.
        elapsedTime = 0
    lastTimeStamp = time.clock()
    return '%.1f seconds' % elapsedTime

# Save the results to a snap graph file.
# TODO: why does snap.SaveEdgeList not save the file?
# TODO: what are we actually saving? Nodes, edges, density?
def saveResults(graph, runTime, density):
    fileName = "greedy-out.tmp"
    print("Saving as " + fileName)
    description = "Densest subgraph by greedy algorithm, completed in " + runTime
    #snap.SaveEdgeList(graph, fileName, description)
    # Write the nodes into a list so that they can be sorted.
    nodeList = []
    for n in graph.Nodes():
        nodeList.append(n.GetId())
    nodeList.sort()

    f = open(fileName, 'w')
    f.write('# Node list of the densest common subgraph of the following graphs:\n')
    for arg in sys.argv[1:]:
        f.write('#   ' + arg + '\n')
    f.write('# Number of nodes: ' + str(len(nodeList)) + '\n')
    f.write('# Density: ' + str(density) + '\n')
    f.write('# Completed in ' + runTime + '\n')
    for n in nodeList:
        f.write(str(n) + '\n')

if(len(sys.argv) < 2):
  sys.exit("Usage: python " + sys.argv[0] + " <file1> <file2> ...")

timer() # Start the timer.
graphs = loadGraphs()
print("Imported " + str(len(graphs)) + " graphs in " + timer())

# If multiple graphs, do some preprocessing to make sure they are over the same
# set of nodes.
if len(graphs) > 1:
    print("Preprocessing...")
    preprocess(graphs)
    # Make sure all graphs have the same amount of nodes.
    # There could be a deeper check here.
    for g in graphs:
        assert g.GetNodes() == graphs[0].GetNodes()
    print(str(graphs[0].GetNodes()) + " nodes are common to all graphs")
    print("Preprocessing took " + timer())

(g2, density) = getDCS_Greedy(graphs)
runTime = timer()
printQuickStats(g2)
print("The greedy algorithm completed in " + runTime)
saveResults(g2, runTime, density)

