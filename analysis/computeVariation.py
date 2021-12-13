#!/usr/bin/env python
# FILE: computeVariation.py
# AUTHOR: Duong Vu
# CREATE DATE: 07 June 2019
import sys, argparse
if sys.version_info[0] >= 3:
	unicode = str
import numpy as np
import os
from Bio import SeqIO
import json
import random
import matplotlib.pyplot as plt
plt.rc('font',size=6)
from matplotlib.patches import Polygon
import numpy as np
import multiprocessing
nproc=multiprocessing.cpu_count()

parser=argparse.ArgumentParser(prog='computeVariation.py',  
							   usage="%(prog)s [options] -i fastafile -c classificationfilename -p classificationposition -mc mincoverage  -o output",
							   description='''Script that computes the median and minimum similarity scores within the groups. ''',
							   epilog="""Written by Duong Vu duong.t.vu@gmail.com""",
   )

parser.add_argument('-i','--input', required=True, help='the fasta file to be clustered.')
parser.add_argument('-mc','--mincoverage', type=int, default=400, help='Minimum sequence alignment length required for BLAST. For short barcode sequences like ITS2 (ITS1) sequences, mc should probably be set to 100.')
parser.add_argument('-o','--out',default="dnabarcoder", help='The output folder.')
parser.add_argument('-c','--classification', help='the classification file in tab. format.')
parser.add_argument('-p','--classificationpos', help='the classification position to load the classification.')
parser.add_argument('-m','--maxSeqNo', type=int, default=0, help='The maximum number of randomly selected sequences of each class to be computed in the case the groups are too big.')
parser.add_argument('-plt','--plottype', default="boxplot", help='The type of plots. There are two options: boxplot and plot.')

args=parser.parse_args()
referencename= args.input
mincoverage = args.mincoverage
classificationfilename=args.classification
jsonvariationfilename =args.out
plottype=args.plottype
maxSeqNo=0
if args.maxSeqNo !=None:
	maxSeqNo=args.maxSeqNo
outputpath=args.out
if not os.path.exists(outputpath):
	os.system("mkdir " + outputpath)	

def GetBase(filename):
	return filename[:-(len(filename)-filename.rindex("."))]

def GetWorkingBase(filename):
	basename=os.path.basename(filename)
	basename=basename[:-(len(basename)-basename.rindex("."))] 
	path=outputpath + "/" + basename
	return path

def LoadClassification(seqIDs,seqrecords,classificationfilename,pos):
	classification=[""]*len(seqIDs)
	classes=[]
	classnames=[]
	rank=""
	if classificationfilename == "":
		return classification,classes,classnames,rank
	records= open(classificationfilename)
	headers=next(records)
	rank=headers.rstrip().split("\t")[pos]
	for line in records:
		elements=line.split("\t")
		seqid = elements[0].replace(">","").rstrip()
		classname=""
		if pos < len(elements):
			 classname=elements[pos].rstrip()
		if classname=="" or classname=="unidentified":
			continue 
		if seqid in seqIDs:
			index=seqIDs.index(seqid)
			if classname in classnames:
				classid=classnames.index(classname)
				classes[classid].append(seqrecords[index])
			else:
				classnames.append(classname)
				seqs=[]
				seqs.append(seqrecords[index])
				classes.append(seqs)
	return classification,classes,classnames,rank

def GetSeqIndex(seqname,seqrecords):
	i=0
	for seqrecord in seqrecords:
		if (seqname == seqrecord.id):
			return i
		i = i + 1
	return -1

def ComputeBLASTscoreMatrix(fastafilename,records,mincoverage):
	scorematrix = [[0 for x in range(len(records))] for y in range(len(records))] 
	seqids=[]
	for rec in records:
		seqids.append(rec.id)
	#blast
	makedbcommand = "makeblastdb -in " + fastafilename + " -dbtype \'nucl\' " +  " -out db"
	os.system(makedbcommand)
	blastcommand = "blastn -query " + fastafilename + " -db  db -task blastn-short -outfmt 6 -out out.txt -num_threads " + str(nproc)
	if mincoverage >=400:
		blastcommand = "blastn -query " + fastafilename + " -db  db -outfmt 6 -out out.txt -num_threads " + str(nproc)
	os.system(blastcommand)
	
	#read blast output
	if not os.path.isfile("out.txt"):
		return scorematrix
	blastoutputfile = open("out.txt")
	refid = ""
	score=0
	queryid=""
	for line in blastoutputfile:
		if line.rstrip()=="":
			continue
		words = line.split("\t")
		queryid = words[0].rstrip()
		refid = words[1].rstrip()
		i = seqids.index(queryid)
		j = seqids.index(refid)
		pos1 = int(words[6])
		pos2 = int(words[7])
		iden = float(words[2]) 
		sim=float(iden)/100
		coverage=abs(pos2-pos1)
		score=sim
		if coverage < mincoverage:
			score=float(score * coverage)/mincoverage
		if scorematrix[i][j] < score:
			scorematrix[i][j]=score
			scorematrix[j][i]=score
	os.system("rm out.txt")
	return scorematrix

def ComputeVariation(reffilename,mincoverage):
	#load sequeces from the fasta files
	records = list(SeqIO.parse(reffilename, "fasta"))
	scorematrix=ComputeBLASTscoreMatrix(reffilename,records,mincoverage)
	scorelist=[]
	for i in range(0,len(scorematrix)-2):
		for j in range(i+1,len(scorematrix)-1):
			if i!=j:
				scorelist.append(scorematrix[i][j])
	threshold=1
	minthreshold=1		
	if len(scorelist) >0:
		x=np.array(scorelist)
		minthreshold=round(float(np.min(x)),4)
		threshold=round(float(np.median(x)),4)
	return threshold,minthreshold

def ComputeVariations(variationfilename,classes,classnames,mincoverage):
	#create json dict
	variations={}
	i=0
	for taxonname in classnames:
		threshold=0
		minthreshold=0
		sequences=classes[i]
		if len(sequences) >0:
			if maxSeqNo==0 or (len(sequences) < maxSeqNo):
				fastafilename=taxonname.replace(" ","_") + ".fasta"
				SeqIO.write(sequences,fastafilename,"fasta")
				threshold,minthreshold=ComputeVariation(fastafilename,mincoverage)
				os.system("rm " + fastafilename)
			else:
				threshold,minthreshold=EvaluateVariation(taxonname,sequences,mincoverage)
			currentvariation=[threshold,minthreshold,len(sequences)]
			variations[taxonname]=currentvariation
		i=i+1	
	#write to file
	with open(variationfilename,"w") as json_file:
		if sys.version_info[0] >= 3:
			json.dump(variations,json_file,indent=2)	
		else:
			json.dump(variations,json_file,encoding='latin1',indent=2)	
	return variations

def EvaluateVariation(taxonname,sequences,mincoverage):
#	thresholds=[]
#	minthresholds=[] 
#	for i in range(0,10):
#		n=int(len(sequences)/10)
#		selectedindexes=random.sample(range(0, len(sequences)), k=n)
#		selectedsequences=[]
#		for index in selectedindexes:
#			selectedsequences.append(sequences[index])
#		fastafilename=taxonname.replace(" ","_") + ".fasta"
#		SeqIO.write(selectedsequences,fastafilename,"fasta")
#		threshold,minthreshold=ComputeVariation(fastafilename,mincoverage)
#		os.system("rm " + fastafilename)
#		thresholds.append(threshold)
#		minthresholds.append(minthreshold)
#	threshold = np.median(np.array(thresholds))
#	minthreshold =  np.min(np.array(minthresholds))
	selectedindexes=random.sample(range(0, len(sequences)), k=maxSeqNo)
	selectedsequences=[]
	for index in selectedindexes:
		selectedsequences.append(sequences[index])
	fastafilename=taxonname.replace(" ","_") + ".fasta"
	SeqIO.write(selectedsequences,fastafilename,"fasta")
	threshold,minthreshold=ComputeVariation(fastafilename,mincoverage)
	return threshold,minthreshold
		
def IndexSequences(filename):
	indexedfilename = GetBase(filename) + ".indexed.fasta"
	fastafile = open(filename)
	indexedfile = open(indexedfilename, "w")
	i=0
	for line in fastafile:
		if line.startswith('>'):
			indexedfile.write(">" + str(i) + "|" + line.rstrip()[1:] + "\n")
			i=i+1
		else:
			indexedfile.write(line)    
	fastafile.close()
	indexedfile.close()
	return indexedfilename

def SaveVariationInTabFormat(output,variation):
	outputfile=open(output,"w")
	outputfile.write("Taxonname\tMedian similarity score\tMin similarity score\tNumber of sequences\n")	
	for classname in variation.keys():
		threshold=variation[classname][0]
		minthreshold=variation[classname][1]
		seqno=variation[classname][2]
		outputfile.write(classname + "\t" + str(threshold) + "\t" + str(minthreshold) + "\t" + str(seqno) + "\n")
	outputfile.close()
	
def Plot(figoutput,variations,rank,displayed):
	#sort variations based on median thresholds with decreasing order
	sorted_variations = sorted(variations.items(), key=lambda x: x[1][0], reverse=True)
	thresholds=[]
	minthresholds=[]
	seqnos=[]
	for item in sorted_variations:
		threshold=item[1][0]
		minthreshold=item[1][1]
		seqno=item[1][2]
		thresholds.append(threshold)
		minthresholds.append(minthreshold)
		seqnos.append(seqno)
	median_median=round(np.median(np.array(thresholds))	,4)
	median_min=round(np.median(np.array(minthresholds))	,4)
	x = np.arange(len(seqnos))
	fig, ax2 = plt.subplots(figsize=(3,3))
	ax = ax2.twinx()  # instantiate a second axes that shares the same x-axi
	ax2.set_ylabel('Number of sequences')  # we already handled the x-label with ax1
	ax2.plot(x, np.array(seqnos), color='g')
	ax.set_title("Median and minimum similarity scores of the " + rank.lower() )
	ax2.set_xlabel("Group index")
	ax.set_ylabel('Similarity score')
	#plt.plot(x, np.array(thresholds), 'r--', x,minthresholds, 'bs') #green 'g^'
	ax.plot(x, np.array(thresholds), 'b--', label=  'Median. Median score' + str(median_median))
	ax.plot(x, np.array(minthresholds), 'rs', label='Min. Median score: ' + str(median_min))
	plt.legend()
	plt.tight_layout()
	plt.rcParams['font.size'] = 6.0
	plt.savefig(figoutput, dpi = 500)
	if displayed==True:
		plt.show()

def PlotAll(figoutput,variationlist,labels):
	data=[]
	for variations in variationlist:
		sorted_variations = sorted(variations.items(), key=lambda x: x[1][0], reverse=True)
		thresholds=[]
		for item in sorted_variations:
			threshold=item[1][0]
			#minthreshold=item[1][1]
			#seqno=item[1][2]
			thresholds.append(threshold)
			#minthresholds.append(minthreshold)
			#seqnos.append(seqno)
		data.append(thresholds)
	colors = plt.cm.Set1(np.linspace(0, 1,len(data)))	
	fig, ax = plt.subplots(figsize=(3,3))
	ax.set_title("Median similarity scores of all groups")
	ax.set_xlabel("Group index")
	ax.set_ylabel('Median similarity score')
	#plt.plot(x, np.array(thresholds), 'r--', x,minthresholds, 'bs') #green 'g^'
	k=0
	for thresholds in data:
		x = np.arange(len(thresholds))
		median_median=np.median(np.array(thresholds))
		ax.plot(x, np.array(thresholds), color=colors[k], label=  labels[k] + '. Median ' + str(median_median))
		k=k+1
	plt.legend()
	plt.tight_layout()
	plt.rcParams['font.size'] = 6.0
	plt.savefig(figoutput, dpi = 500)
	plt.show()
	
def BoxPlot(figoutput,variations,rank,displayed):
	#sort variations based on median thresholds with decreasing order
	sorted_variations = sorted(variations.items(), key=lambda x: x[1][0], reverse=True)
	thresholds=[]
	minthresholds=[]
	seqnos=[]
	for item in sorted_variations:
		threshold=item[1][0]
		minthreshold=item[1][1]
		seqno=item[1][2]
		thresholds.append(threshold)
		minthresholds.append(minthreshold)
		seqnos.append(seqno)
	labels=["Median", "Min"]	
	data=[np.array(thresholds),np.array(minthresholds)]
#	fig, ax = plt.subplots(figsize=(10, 6))
#	#fig.canvas.set_window_title('Variation')
#	fig.subplots_adjust(left=0.075, right=0.95, top=0.9, bottom=0.25)
	fig, ax = plt.subplots(figsize=(3,3))
	box_colors = ['b','r']#['darkkhaki', 'royalblue']
	bp = ax.boxplot(data, notch=0, sym='+', vert=1, whis=1.5)
	plt.setp(bp['boxes'], color='black')
	plt.setp(bp['whiskers'], color='black')
	plt.setp(bp['fliers'], color='red', marker='+')
	
	ax.yaxis.grid(True, linestyle='-', which='major', color='lightgrey',
               alpha=0.5)

	# Hide these grid behind plot objects
	ax.set_axisbelow(True)
	ax.set_title('Median and min. similarity scores of ' + rank)
	#ax.set_xlabel('')
	ax.set_ylabel('Similarity score')
	num_boxes=len(data)
	medians=np.empty(num_boxes)
	for i in range(num_boxes):
		box=bp['boxes'][i]
		boxX=[]
		boxY=[]
		for j in range(5):
			boxX.append(box.get_xdata()[j])
			boxY.append(box.get_ydata()[j])
		box_coords = np.column_stack([boxX, boxY])	
		# Fill in the color
		ax.add_patch(Polygon(box_coords, facecolor=box_colors[i % 2]))
		med = bp['medians'][i]
		medianX=[]
		medianY=[]
		for j in range(2):
			medianX.append(med.get_xdata()[j])
			medianY.append(med.get_ydata()[j])
		medians[i] = medianY[0]
		#plot the average value
		ax.plot(np.average(med.get_xdata()), np.average(data[i]),color='w', marker='*', markeredgecolor='k')
	#add labels	
	ax.set_xticklabels(np.array(labels))	
	#add median values 
	upper_labels = [str(np.round(s, 4)) for s in medians]
	pos = np.arange(num_boxes) + 1
	k=0
	for tick, label in zip(range(num_boxes), ax.get_xticklabels()):
		ax.text(pos[tick], 0.97, upper_labels[tick], transform=ax.get_xaxis_transform(), horizontalalignment='center', size='x-small', color=box_colors[k])
		k=k+1
	#plt.legend()
	plt.tight_layout()
	plt.rcParams['font.size'] = 6.0
	plt.savefig(figoutput, dpi = 500)
	if displayed==True:
		plt.show()
		
def BoxPlotAll(figoutput,variationlist,labels):
	data=[]
	labels2=[]
	colors=[]
	i=0
	for variations in variationlist:
		sorted_variations = sorted(variations.items(), key=lambda x: x[1][0], reverse=True)
		thresholds=[]
		minthresholds=[]
		for item in sorted_variations:
			threshold=item[1][0]
			minthreshold=item[1][1]
			#seqno=item[1][2]
			thresholds.append(threshold)
			minthresholds.append(minthreshold)
			#seqnos.append(seqno)
		data.append(thresholds)
		data.append(minthresholds)
		labels2.append("Median_" + labels[i])
		labels2.append("Min_" + labels[i])
		colors.append('b')
		colors.append('r')
		i=i+1
#	fig, ax = plt.subplots(figsize=(10, 6))
#	#fig.canvas.set_window_title('Variation')
#	fig.subplots_adjust(left=0.075, right=0.95, top=0.9, bottom=0.25)
	#box_colors = ['r','b']#['darkkhaki', 'royalblue']
	fig, ax = plt.subplots(figsize=(3,3))
	bp = ax.boxplot(data, notch=0, sym='+', vert=1, whis=1.5)
	plt.setp(bp['boxes'], color='black')
	plt.setp(bp['whiskers'], color='black')
	plt.setp(bp['fliers'], color='red', marker='+')
	
	ax.yaxis.grid(True, linestyle='-', which='major', color='lightgrey', alpha=0.5)
	# Hide these grid behind plot objects
	ax.set_axisbelow(True)
	ax.set_title('Median and min. similarity scores of all groups')
	#ax.set_xlabel('')
	ax.set_ylabel('Similarity score')
	num_boxes=len(data)
	#colors = plt.cm.Set1(np.linspace(0, 1,num_boxes))
	medians=np.empty(num_boxes)
	for i in range(num_boxes):
		box=bp['boxes'][i]
		boxX=[]
		boxY=[]
		for j in range(5):
			boxX.append(box.get_xdata()[j])
			boxY.append(box.get_ydata()[j])
		box_coords = np.column_stack([boxX, boxY])	
		# Fill in the color
		ax.add_patch(Polygon(box_coords, facecolor=colors[i]))
		med = bp['medians'][i]
		medianX=[]
		medianY=[]
		for j in range(2):
			medianX.append(med.get_xdata()[j])
			medianY.append(med.get_ydata()[j])
		medians[i] = medianY[0]
		#plot the average value
		ax.plot(np.average(med.get_xdata()), np.average(data[i]),color='w', marker='*', markeredgecolor='k')
	#add labels	
	ax.set_xticklabels(np.array(labels2), rotation=90)	
	#add median values 
	upper_labels = [str(np.round(s, 4)) for s in medians]
	pos = np.arange(num_boxes) + 1
	k=0
	for tick, label in zip(range(num_boxes), ax.get_xticklabels()):
		ax.text(pos[tick], 0.97, upper_labels[tick], transform=ax.get_xaxis_transform(), horizontalalignment='center', size='x-small', color=colors[k])
		k=k+1
	#plt.legend()
	plt.tight_layout()
	plt.rcParams['font.size'] = 6.0
	plt.savefig(figoutput, dpi = 500)
	plt.show()		

	
##############################################################################
# MAIN
##############################################################################
path=sys.argv[0]
path=path[:-(len(path)-path.rindex("/")-1)]
displayed=True
poslist=[]

if args.classificationpos==None or args.classificationpos=="":
	classificationfile=open(classificationfilename)
	firstline=classificationfile.readline()
	classificationfile.close()
	rankNo=len(firstline.split("\t"))
	for i in range(1,rankNo):
		poslist.append(i)
	displayed=False
elif "," in args.classificationpos:
	texts=args.classificationpos.split(",")
	for t in texts:
		poslist.append(int(t))
	displayed=False	
else:
	poslist.append(int(args.classificationpos))
	
#load train seq records
referencerecords =  list(SeqIO.parse(referencename, "fasta"))
referenceIDs=[]
for seq in referencerecords:
	referenceIDs.append(seq.id)
variationlist=[]
labels=[]
rank=""
for classificationposition in poslist:
	jsonvariationfilename = GetWorkingBase(referencename) + "." + str(classificationposition) + ".variation"
	figoutput=GetBase(jsonvariationfilename) + ".variation.png" 
	#Load classes, classification:
	referenceclassification,classes,classnames,rank= LoadClassification(referenceIDs,referencerecords,classificationfilename, classificationposition)
	if rank=="":
		rank="groups at position " + str(classificationposition)
	elif rank.lower()== "family":
		rank="families"
	elif rank.lower()== "order":
		rank="orders"
	elif rank.lower()== "class":
		rank="classes"
	elif rank.lower()== "phylum":
		rank="phyla"
	elif rank.lower()== "kingdom":
		rank="kingdoms"		
	variations={}
	if not os.path.exists(jsonvariationfilename):
		variations=ComputeVariations(jsonvariationfilename,classes,classnames,mincoverage)
	else:
		print("The variation file " + jsonvariationfilename + " exists. Please delete the file if you wish to recalculate the variation.")
		with open(jsonvariationfilename) as variation_file:
			variations = json.load(variation_file)
		SaveVariationInTabFormat(jsonvariationfilename + ".txt",variations)
		print("The variations are saved in the json file  " + jsonvariationfilename + " and tab file " + jsonvariationfilename + ".txt. The figure is saved in " + figoutput + "."  )
		#plot
		if plottype=="plot":
			Plot(figoutput,variations,rank,displayed)
		else:	
			BoxPlot(figoutput,variations,rank,displayed)
	variationlist.append(variations)
	labels.append(rank)		
if len(poslist)>1:
	jsonvariationfilename = GetWorkingBase(referencename) + ".variation"
	figoutput=jsonvariationfilename + ".png" 
if plottype=="plot":
	PlotAll(figoutput,variationlist,labels)
else:	
	BoxPlotAll(figoutput,variationlist,labels)
print("All variations and theirs figure are saved in file " + jsonvariationfilename + " and " + figoutput + ".")
			

