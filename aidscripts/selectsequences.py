#!/usr/bin/env python
# FILE: selectsequences.py
# AUTHOR: Duong Vu
# CREATE DATE: 07 June 2020
import sys
import numpy as np
import os, argparse
from Bio import SeqIO
import json
import multiprocessing
nproc=multiprocessing.cpu_count()
#from keras.utils import np_utils

parser=argparse.ArgumentParser(prog='selectsequences.py', 
							   usage="%(prog)s [options] -i fastafile -c classificationfile -rank species -t taxa -o output",
							   description='''Script that selects the sequences for of the given taxa. The taxon names in the taxa are separated by ","''',
							   epilog="""Written by Duong Vu duong.t.vu@gmail.com""",
   )

parser.add_argument('-i','--input', required=True, help='the fasta file')
parser.add_argument('-o','--out', required=True, help='The fasta output file containing the sequences of the given taxa.') #optional
parser.add_argument('-c','--classification', default="", help='the classification file in tab. format.')
parser.add_argument('-t','--taxa', default="", help='the taxa for the selection, separated by ","')
parser.add_argument('-n','--number', type=int, default=0, help='the maximum number of the sequences to be selected')
parser.add_argument('-rank','--classificationrank', default="", help='the classification rank for the selection.')
parser.add_argument('-l','--length', type=int, default=0, help='the required minimum length.')
parser.add_argument('-idcolumnname','--idcolumnname',default="ID", help='the column name of sequence id in the classification file.')

args=parser.parse_args()
fastafilename= args.input
classificationfilename=args.classification
taxa=args.taxa
output=args.out
n=args.number
l=args.length
classificationrank=args.classificationrank

#fastafilename=sys.argv[1]
#taxa=sys.argv[2] #separated by ;
#classificationfilename = sys.argv[3]
#output=sys.argv[4]

def GetBase(filename):
	return filename[:-(len(filename)-filename.rindex("."))]

def GetPosition(classificationfilename,rank):
	pos=-1
	seqidpos=-1
	classificationfile=open(classificationfilename)
	header=classificationfile.readline()
	header=header.rstrip()
	classificationfile.close()
	texts=header.rstrip().split("\t")
	i=0
	for text in texts:
		if text.lower()==args.idcolumnname.lower():
			seqidpos=i
		i=i+1
	if 	seqidpos==-1:
		print("Please specify the sequence id columnname by using -idcolumnname.")
		isError=True
	isError=False
	if rank in texts:
		pos=texts.index(rank)
	else:
		print("The rank " + rank + " is not given in the classification." )
		isError=True
	return seqidpos,pos,isError

def LoadClassification(classificationfilename,taxa,classificationpos,seqidpos):
	if not os.path.exists(classificationfilename):
		return {}
	classnames={}
	taxalist = []
	if "," in taxa:
		taxalist = taxa.split(",")
	elif taxa != "" and taxa != "unidentified":
		taxalist.append(taxa)
	classificationfile = open(classificationfilename)
	for line in classificationfile:
		elements = line.rstrip().split("\t")
		seqid = elements[seqidpos].rstrip()
		classname = ""
		if classificationpos >= 0 and classificationpos < len(elements):
			classname = elements[classificationpos]
		if classname == "" or classname == "unidentified":
			continue
		if taxa != "":
			for taxonname in taxalist:
				if taxonname != "" and taxonname != "unidentified":
					if taxonname in elements:
						classnames.setdefault(seqid,classname)
		else:
			classnames.setdefault(seqid,classname)
	return classnames

def GetTaxonName(description,rank):
	taxonname=""
	species=""
	genus=""
	family=""
	order=""
	bioclass=""
	phylum=""
	kingdom=""
	if " " in description:
		description=description.split(" ")[1]
	texts=description.split("|")
	for text in texts:
		text=text.rstrip()
		taxa=text.split(";")
		for taxon in taxa:
			if taxon.startswith("k__"):
				kingdom=taxon.replace("k__","")
			elif taxon.startswith("p__"):
				phylum=taxon.replace("p__","")
			elif taxon.startswith("c__"):
				bioclass=taxon.replace("c__","")
			elif taxon.startswith("o__"):
				order=taxon.replace("o__","")
			elif taxon.startswith("f__"):
				family=taxon.replace("f__","")
			elif taxon.startswith("g__"):
				genus=taxon.replace("g__","")
			elif taxon.startswith("s__") and (" " in taxon.replace("s__","") or "_" in taxon.replace("s__","")):
				species=taxon.replace("s__","")
				species=species.replace("_"," ")
	if rank.lower()=="species":
		taxonname=species
	elif rank.lower()=="genus":
		taxonname=genus
	elif rank.lower()=="family":
		taxonname=family
	elif rank.lower()=="order":
		taxonname=order
	elif rank.lower()=="class":
		taxonname=bioclass
	elif rank.lower()=="phylum":
		taxonname=phylum
	elif rank.lower()=="kingdom":
		taxonname=kingdom
	return taxonname

def SelectClassName(seqid,description,rank,taxa,classnames):
	classname=""
	taxalist=[]
	if "," in taxa:
		taxalist=taxa.split(",")
	elif taxa!="" and taxa!="unidentified":
		taxalist.append(taxa)
	if classnames=={}:
		classname=GetTaxonName(description,rank)
		if classname=="unidentified":
			classname=""
	else:
		try:
			classname=classnames[seqid]
		except KeyError:
			pass
	if taxa != "" and classname!="":
		if not (classname in taxalist):
			classname = ""
	return classname

#####main###
classificationpos=-1
seqidpos=-1
classnames={}
if classificationfilename!="":
	seqidpos,classificationpos,isError=GetPosition(classificationfilename,classificationrank)
	if isError==True:
		os.sys.exit()
	classnames=LoadClassification(classificationfilename,taxa,classificationpos,seqidpos)
seqrecords=SeqIO.to_dict(SeqIO.parse(fastafilename, "fasta"))
selectedrecords=[]
selectedclassnames={}
for seqid in seqrecords.keys():
	seqrec=seqrecords[seqid]
	description=seqrec.description
	classname=SelectClassName(seqid,description,classificationrank,taxa,classnames)
	if classname != "":
		if n==0: #no limit for number of sequences for a group
			if len(str(seqrec.seq)) >= l: # the length of the sequence must be >=l
				selectedrecords.append(seqrec)
		else:
			if not classname in selectedclassnames.keys():
				selectedclassnames.setdefault(classname,0)
			if 	selectedclassnames[classname] <n:
				if len(str(seqrec.seq))>l:
					selectedclassnames[classname]=selectedclassnames[classname]+1
					selectedrecords.append(seqrec)
#save to file:
SeqIO.write(selectedrecords,output,"fasta")
if len(selectedrecords) >0:
	print("The selected sequences are saved in " + output + ".")
else:
	print("No sequences are selected.")

