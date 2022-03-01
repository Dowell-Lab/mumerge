import sys
sys.path.append('C:\\Users\\Jacob\\Dropbox\\0DOWELL\\muMerge\\mumerge\\')
import argparse
import numpy as np
from os import system
from time import time
from socket import gethostname
from operator import mul
from math import ceil
from collections import defaultdict
from collections import Counter
from functools import reduce
from itertools import combinations
from pathlib import Path

#import mumerge_test_unit as mt

### SOME LOW LEVEL FUNCTIONS THAT GET UTILIZED IN THE MAJOR FUNCTIONS #########
def normal(x, pos, sig, scale):
    '''
    Calculates the value of a normalized gaussian (can include additional 
    scaling value)
    '''
    arg = ((x - pos) / sig) ** 2 / 2.0
    coeff = scale / np.sqrt(2 * np.pi) / sig
    return coeff * np.exp(-arg)


def overlap_check(a, b):
    '''
    Check to see if the two ordered tuples, 'a' and 'b', overlap with one 
    another
    '''
    val = (a[0] - b[1]) * (a[1] - b[0])
    if val < 0:
        return True
    else:
        return False


def chromesome_list():
    '''
    Returns a list of chromesome strings. This just helps standardize the list 
    across various functions.
    '''
    chromesome_list = [i for i in range(1,23)] + ["X", "Y"]
    chromesome_list = ["chr" + str(i) for i in chromesome_list]
    return chromesome_list


def closest_idx(val, loc_list):
    '''
    Returns index of the position in the list loc_list closest to val
    '''
    diff = [abs(val - e) for e in loc_list]
    closest_index = diff.index(min(diff))
    return closest_index


def prod(iterable):
    '''
    This is the product equivalent of sum(). It requires functools reduce() and
    operator module. Apparently this is also in numpy...
    '''
    return reduce(mul, iterable)


def normalizer(values, scaler=1, integral=False):
    '''
    This function either scales the max value or the sum to a given value
    (scaler)
    '''
    if integral == False:
        max_val = max(values)
        scaled_values = [y * scaler / max_val for y in values]
    else:
        sum_val = sum(values)
        scaled_values = [y * scaler / sum_val for y in values]

    return scaled_values


###############################################################################
# This function processes the initial inputs by arg parsing, defining variables
# and then generating the merged bedfile from the inputted sample bedfiles.
# This function is just a container for the code and doesn't take any inputs 
# (acts only on the global variables)
def inputs_processor():
    '''
    Input: Global variables from stdin
    Output: bedfiles (list), sample ID's (list), groups (list of lists), and 
            merged bedfile name (string), in that order.
    '''
    description_text = ("Merges region calls (mu) generated by Tfit, or other "
        "peak calling functions across multiple samples and replicates.")

    input_help = ("Input file (full path) containing bedfiles, sample ID's "
        "and replicate grouping names (tab delimited). Each sample on "
        "separate line. First line header, equal to "
        "'#file<TAB>sampid<TAB>group', required. 'file' must be full path. "
        "'sampid' can be any string. 'group' can be string or integer. See "
        "'-H' help flag for more information.")
    input_format = ("\nInput file containing bedfiles, sample ID's, and "
        "replicate groupings. Input\nfile (indicated by the '-i' flag) "
        "should be of the following (tab delimited)\nformat:\n\n"
        "#file\tsampid\tgroup\n"
        "/full/file/path/filename1.bed\tsampid1\tA\n"
        "/full/file/path/filename2.bed\tsampid2\tB\n"
        "...\n\n")
    input_details = ("Header line indicated by '#' character must be included "
        "and fields must\nfollow the same order as non-header lines. The "
        "order of subsequent lines does\nmatter. 'group' identifiers should "
        "group files that are technical/biological\nreplicates. Different "
        "experimental conditions should recieve different 'group'\n"
        "identifiers. The 'group' identifier can be of type 'int' or 'str'. "
        "If 'sampid'\nis not specified, then default sample ID's will be "
        "used.\n")

    # This dictionary stories all the parsed and processed args
    outdict = {
        'input': None,
        'bedfiles': [],
        'sampids': [],
        'groupings': [],
        'merged': None,
        'output': None,
        'weights': None,
        'verbose': False,
        'remove_singletons': False,
        'width_ratio': None
    }

    parser = argparse.ArgumentParser(description=description_text)

    # ADDITIONAL HELP TEXT FLAG
    parser.add_argument(
        '-H', '--HELP', 
        action='store_true', 
        help="Verbose help info about the input format."
    )
    # INPUT FILE ARG (contains bedfiles, sampids, and groupings)
    parser.add_argument(
        '-i', '--input', 
        type=str, 
        help=input_help
    )
    # OUTPUT PATH/FILENAME
    parser.add_argument(
        '-o', '--output', 
        type=str, 
        help=("Output file basename (full path, sans extension). WARNING: "
            "will overwrite any existing file)")
    )
    # WIDTH RATIO (1/2-WIDTH-BED / PROB SIG)
    parser.add_argument(
        '-w', '--width',
        type=float,
        help=("The ratio of a the sigma for the corresponding probabilty "
            "distribution to the bed region (half-width) --- sigma:half-bed "
            "(default: 1). The choice for this parameter will depend on "
            "the data type as well as how bed regions were inferred from the "
            "expression data."),
        default=1.0
    )
    # PRECOMPILED MERGE BEDFILE (OPTIONAL)
    parser.add_argument(
        '-m', '--merged',
        type=str,
        help=("Sorted bedfile (full path) containing the regions over which "
            "to combine the sample bedfiles. If not specified, mumerge will "
            "generate one directly from the sample bedfiles.")
    )
    # VERBOSE TOGGLE (OPTIONAL)
    parser.add_argument(
        '-r', '--remove_singletons',
        action='store_true',
        help="Remove calls not present in more than 1 sample"
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help="Verbose printing during processing."
    )
    args = parser.parse_args()

    # If -H is specified, print out additional help text and exit
    if args.HELP:
        print(input_format +  input_details)
        sys.exit()

    if args.verbose:
        outdict['verbose'] = True

    if args.remove_singletons:
        outdict['remove_singletons'] = True
    
    if not args.output:
        raise TypeError("Please specify output filename with '-o' flag. "
                        "Shound include fullpath + basename for outputs. "
                        "Check help menu for further information.")

    if args.input:
        outdict['input'] = args.input
        with open(args.input, "r") as f:
            header = f.readline().strip().lstrip('#').split("\t")

            # Determine which columns correspond to what
            for i, col in enumerate(header):
                if col == 'file':
                    filename_col = i
                elif col == 'sampid':
                    sampid_col = i
                elif col == 'group':
                    group_col = i
                else:
                    raise ValueError("Header only contains 'file', 'sampid' "
                                    ", and/or 'group' (tab delimited).")
            
            # Append all samples to list of tuples (and checking length)
            samples = []
            for line in f:
                samp = tuple(line.strip().split("\t"))
                assert len(samp) == 3, "Sample line must contain three fields."
                samples.append(samp)
            
            # Assign bedfiles and sampids (input must have 3 columns)
            bedfiles, sampids, groups = zip(*samples)

            # Pull set of groups and initialize list to contain group structure
            groups = sorted(set(groups))
            grouped_samps = []
            # Loop over all group names
            for group in groups:
                samp_group = []
                # Loop over all samples and assign their samp ID's to group
                for sample in samples:
                    if sample[group_col] == group:
                        samp_group.append(sample[sampid_col])
                grouped_samps.append(sorted(samp_group))

            # if/else to determine how to handle merged bedfile
            if args.merged:
                # User defined bedfile
                union_bedfile = args.merged
            else:
                # Generate merged bed file using bedtools binary
                srcdir = Path(__file__).absolute().parent

                union_bedfile = args.output + "_BEDTOOLS_MERGE.bed"
                bedtools = "".join([str(srcdir), "/bin/bedtools"])

                cat = "cat " + " ".join(bedfiles)
                sort = " ".join(["|", bedtools, "sort -i stdin"])
                merge = " ".join(["|", bedtools, "merge -i stdin"])
                out = " ".join([">", union_bedfile])

                system(" ".join([cat, sort, merge, out]))

#                os.system("cat " + " ".join(bedfiles)
#                    + " | bedtools sort -i stdin | bedtools merge -i stdin > "
#                    + union_bedfile)

    else:
        raise TypeError("Please specify input file with '-i' flag. "
                        "For more details run mumerge with the '-H' flag.")

    # Assign the parsed+processed args to the output dict
    outdict['bedfiles'] = bedfiles
    outdict['sampids'] = sampids
    outdict['groupings'] = grouped_samps
    outdict['merged'] = union_bedfile
    outdict['output'] = args.output
    outdict['weights'] = None
    outdict['width_ratio'] = args.width

    return outdict


###############################################################################
def log_initializer(
        input_file,
        tfit_filenames, 
        outbed_filename,
        union_bedfile, 
        miscallfilename, 
        output_basename,
        logfile, 
        miscallfile, 
        sampids, 
        groupings
):
    '''
    This function writes all the header/preamble info to the miscalls and log
    files.
    '''
    # Write to miscall and log files
    miscallfile.write("# This file contains regions which were identified not "
                    "to contain a tfit call after merging. Hand check these.")

    logfile.write("Running: {}\n".format(sys.argv[0]))
    logfile.write("Python:\n{}\n".format(sys.version))
    logfile.write("Hostname: {}\n".format(gethostname()))
    logfile.write("\n# Sample_ID \t Filename\n")

    for i, f in enumerate(tfit_filenames):
        f_path = Path(f)
        logfile.write("{} \t {}\n".format(sampids[i], f_path.absolute()))

    input_path = Path(input_file)
    logfile.write("\ninput file: {}\n".format(input_path.absolute()))
    out_basename_path = Path(output_basename)
    logfile.write("output path: {}\n".format(out_basename_path.absolute()))
    logfile.write("'bedtools merge' bedfile: {}\n".format(union_bedfile))
    logfile.write("miscalls bedfile: {}\n".format(miscallfilename))
    logfile.write("muMerge output bedfile: {}\n".format(outbed_filename))
    

    logfile.write("\nGroupings:\n")
    for i , group in enumerate(groupings):
        logfile.write("{}\t{}\n".format(i, group))


###############################################################################
# This function reads a bed file into a list of tuples, to be used as input
# "interest_regions" in tfit_dict_initializer()
def bedfile_reader(file, bedGraph=False, print_header=False, count=False):
    '''
    This reads in a bedfile and outputs the lines as a list of tuples of the
    form [('chr#', start, stop), ...]. Additional columns can be provided, but
    will be ignored if bedGraph=False. If True, fourth column will be
    interpreted as coverage.

    TODO: Incorporate the bedGraph functionality, write docstring
    '''
    with open(file) as f:
            # Initialize output list and counter
            bed_list = []
            counter = 1

            # Loop over the header lines and print them out until line without
            # '#' is encountered, then split it
            line = f.readline().strip('\n')
            while line[0] == '#':
                if print_header == True:
                    print(line)
                line = f.readline().strip('\n')
            line = line.split('\t')

            chromesome = line[0]
            start = int(line[1])
            stop = int(line[2])
            bed_list.append((chromesome, start, stop))

            # Loop over all the lines in bed file and add to list
            for line in f:

                # Read and split non-header lines. Lines should be of the form 
                # "chr#  start  stop  [cov  [parameters]]"
                line = line.strip('\n').split('\t')
                chromesome = line[0]
                start = int(line[1])
                stop = int(line[2])
                bed_list.append((chromesome, start, stop))
                counter = counter + 1

    if count == True:
        print("Number of regions: ", counter)
        return bed_list, counter
    else:
        return bed_list


###############################################################################
### USED IN MU_DICT_GENERATOR() 
###############################################################################
# This function initializes the tfit dictionary
def tfit_dict_initializer(interest_regions, 
                          chromesome_flag=True,
                          bed_region_flag=True):
    '''
    Initializes a dictionary to store grouped tfit calls. Currently only has 
    one format {'chr#': {(start, stop): [...]}}. Interest regions must be of 
    the form [('chr#', start, stop), ...]
    '''
    tfit_dict = defaultdict(dict)

    if chromesome_flag == True:
        for chromesome in chromesome_list():
            tfit_dict[chromesome] = {}

    if (chromesome_flag == True and bed_region_flag == True):
        for region in interest_regions:
            chromesome = region[0]
            start = int(region[1])
            stop = int(region[2])

            tfit_dict[chromesome][(start, stop)] = []             
    return tfit_dict


###############################################################################
# This function scans a single tfit file and populates the tfit call regions 
# into the provided dict
def tfit_file_reader(filename, sampid, tfit_dict):
    '''
    This function scans a tfit file and populates the tfit call regions into 
    the provided dict and returns that dict with the updated information. Must 
    provide a sample ID.
    TODO: This function is computationally intensive (I think). Might be the
    bottleneck. I should reevaluate the 'region_key = next()' approach
    '''
    with open(filename, 'r') as f:
            
            # Loop over the header lines and print them out
            line = f.readline().strip('\n')
            while line[0] == '#':
                #print(line)
                line = f.readline().strip('\n')

            # First non-header line
            line = line.split('\t')
            chromesome = line[0]
            start = int(line[1])
            stop = int(line[2])
            coverage = 0

            try:
                region_key = next(
                    key for key in tfit_dict[chromesome].keys()
                    if start >= int(key[0]) and stop <= int(key[1])
                    )
                val = tuple([start, stop, coverage, sampid])
                tfit_dict[chromesome][region_key].append(val)
            except Exception:
                print("No region found...")     # CHANGE THIS!!!

            # Loop over all the lines in tfit file and compare the to regions 
            # in dict
            for line in f:

                # Read and split non-header lines. Lines should be of the form 
                # "chr#  start  stop  [parameters]"
                line = line.strip('\n').split('\t')
                chromesome = line[0]
                start = int(line[1])
                stop = int(line[2])
                coverage = 0
        
                # Find start_stop_key in which the start_stop region in the 
                # line lands
                try:
                    region_key = next(
                        key for key in tfit_dict[chromesome].keys()
                        if start >= int(key[0]) and stop <= int(key[1])
                        )
                    val = tuple([start, stop, coverage, sampid])
                    tfit_dict[chromesome][region_key].append(val)
                except StopIteration:
                    continue
    return tfit_dict


###############################################################################
# This function reads in, from an input path, a list of tfit output files and 
# a list of regions within these files to check for tfit calls. It outputs a 
# dict of the form 
# {'chr#' : {(start, stop) : [(mu_start, mu_stop, cov, 'ID'), ...]}}
# constraints: 1) tfit_filenames and "sampid" must be lists that have 1-to-1 
#                 correspondence
#            2) "interest_regions" must be a list of tuples with first three 
#               terms being ('chr#', 'start_pos', 'stop_pos)
#            3) ...
def mu_dict_generator(tfit_filenames, 
                      interest_regions, 
                      sampids = ["sampid_NA"],
                      verbose = False):
    '''
    At its core this function calls tfit_dict_initializer() on the interest 
    regions (i.e. the results of bedtools merge) and then loops over a list of 
    sample tfit files, calling tfit_file_reader() on each one and subsequently 
    appending the results to the output dict 'tfit_dict'.

    TODO: 1) write docstring, 2) incorporate ability to read in actual tfit 
    model, 3) fix next() issue...
    '''
    
    assert isinstance(tfit_filenames, (list, tuple)), (
        "'tfit_filenames' must be of type 'list'")
    assert isinstance(sampids, (list, tuple)), (
        "'sampid' must be of type 'list'")

    # create list of default sampID's if non-provided, or use same ID provided 
    # for all samples
    if sampids == ["sampid_NA"]:
        sampids = [sampids[0] for i in tfit_filenames]
        if verbose:
            print(("WARNING: No 'sampids' provided. "
                   "Using {0} for all ID's.\n").format(sampids[0]))
    
    # If sample ID's are provided but not right length, print warning
    elif sampids != "sampid_NA" and len(sampids) != len(tfit_filenames):
        sampids = [sampids[0] for i in tfit_filenames]
        if verbose:
            print(("WARNING: Length of 'sampids' does not match "
                   "'tfit_filenames'. Using {0} for all ID's.\n")
                   .format(sampids[0]))
    
    # Print out sample ID's and their corresponding filenames
    else:
        if verbose:
            print("# Sample_ID \t Filename")
            for i, file in enumerate(tfit_filenames):
                print("#", sampids[i], " \t", file)
    
    # Initialize the bedfile dictionary {"chr#" : {(start, stop) : []}} 
    # using "interest_regions" list
    tfit_dict = tfit_dict_initializer(interest_regions)

    # Zip together sample id's with filenames (both strings)
    id_and_files = list(zip(sampids, tfit_filenames))
    
    #Loop over all the filenames in the tfit_filenames list and scan through 
    # each one (tfit_file_reader() is user defined)
    for (sampid, file) in id_and_files:
        tfit_dict = tfit_file_reader(file, sampid, tfit_dict)
    
    return dict(tfit_dict)


###############################################################################
# This function will be used to filter out singletons and low coverage calls 
# to increase overall call quality. 
def call_remover(mu_list,remove_singletons):
    '''
    This function removes calls that only appear in one sample
    (Later this will be the function that removes low quality/low
    coverage calls as well)
    '''
    # Check whether there is more than 1 entry at that region                  # (should we do this as >=1 region/replicate instead?)
    if remove_singletons:
        if len(mu_list) == 1:
            return True
        else:
            return False


# This function generates the list of y-values at the corresponding x-values 
# for a given distribution
def prob_list_generator(xvals, params=None, dist="normal", width=1.0):
    '''
    This generates the y-values for the distribution of a mu tfit call. This 
    list should be the same length and order as the xvals list. The values
    should be normalized to the number of mu calls in that region.

    calls: normal()
    '''
    if dist == "normal":
        mu_pos = round((params[1] + params[0]) / 2)

        # sigma = (1/2-bed region) * width_ratio
        mu_sig = ((params[1] - params[0]) / 2 ) * width                        # THIS IS A KEY FACTOR IN INTERPRETTING TFIT INTERVALS!!

        # evaluate the normal dist at all points in xvals
        y_i = [normal(x, mu_pos, mu_sig, 1) for x in xvals]
    elif dist == "uni":
        y_i = (1 if x >= params[0] and x <= params[1] else 0 for x in xvals)
    else:
        raise ValueError("Must specify either 'normal' or 'uni' for 'dist'")
    return y_i


###############################################################################
# THIS IS ONE OF THE TWO FUNCTIONS I'M USING TO AVOID SOME LOGICAL CHECKS IN 
# THE PROB_CALCULATOR()
def prob_product(sample_prob_list):
    '''
    This just calculates the product of a list of probabilty lists
    '''
    #joint_prob_id = "Joint_Prob"
    joint_prob_list = [prod(i) for i in zip(*sample_prob_list)]
    return joint_prob_list


# THIS IS ONE OF THE TWO FUNCTIONS I'M USING TO AVOID SOME LOGICAL CHECKS IN 
# THE PROB_CALCULATOR()
def prob_sum(sample_prob_list):
    '''
    This calculates the sum of a list of probability lists
    '''
    #joint_prob_id = "Cummulative_Prob"
    joint_prob_list = [sum(i) for i in zip(*sample_prob_list)]
    return joint_prob_list


###############################################################################
# This function generates lists of probabilities values from the tfit_dict 
# (mu, sig)
def prob_list_formatter(region, mu_list, dist="normal", width=1.0):
    '''
    DOCSTRING
    This function sort of supplants the mu_viz_prep() function I wrote in the
    jupyter notebook
    calls: prob_list_generator()?
    TODO: Rewrite docstring
    '''
    # Define base position values in the region
    xvals = [x for x in  range(region[0], region[1])]

    # Unzip the input mu_list. mu_list should be list of tuples of format 
    # (start, stop, cov, 'sampID')
    try:
        starts, stops, cov, samples = zip(*mu_list)
        samp_list = sorted(set(samples))
    except TypeError:
        print(("'mu_list' is not of the right format -- list of tuples" 
              "(start, stop, cov, 'sampID')"))

    # Intermediate dict, to grop together all the values for each sample
    region_dict = defaultdict(list)
    region_dict = {sample : [] for sample in samp_list}

    # Loop over all the mu in the initial mu_list input and generate a y_i 
    # array for either normal or uni distributions
    for mu in mu_list:
        values = prob_list_generator(xvals, mu, dist=dist, width=width)
        id = mu[3]
        region_dict[id].append(values)

    # Collapse all the lists for each sample into a single probability list
    for id, probs in region_dict.items():
        region_dict[id] = prob_sum(probs)

    return dict(region_dict)


###############################################################################
# This function calculates joint/cummulative probabilties for two or more 
# equal length lists of probabilty data
def combined_prob_calculator(sample_prob_dict, groups=None):
    '''
    This calculates the combined probability by taking the product WITHIN 
    groups and sum BETWEEN groups. This assumes that each of the probability 
    lists contained in sample_prob_dict have been properly normalized. 
    
    'sample_prob_dict' of the form {'sampID': [y_1, ..., y_i]} where y_i are
    probability values for positions x_i
    'groups' are of the form 
    [[cond1_rep1, cond1_rep2, ...], [cond2_rep1, cond2_rep2, ...], ...] 
    where each element is a string corresponding to the sampleID for that 
    particular sample.

    Calls: normalizer()?
    TODO: Update docstring, code review of commented out lines
    NOTE: THE WEIGHTING SCHEME COULD BE ADDED INTO THIS FUNCTION
    '''
    # First, define a uniform dist to be added for samples with no tfit calls
    list_len = len(list(sample_prob_dict.values())[0])
    uni_list = [1 / list_len for i in range(list_len)]

    cond_list = []
    for condition in groups:
        rep_list = []
        rep_num = len(condition)
        counter = 0
        for replicate in condition:
            if replicate in sample_prob_dict.keys():
                rep_list.append(sample_prob_dict[replicate])
            else:
                rep_list.append(uni_list)
                counter = counter + 1

        rep_product = prob_product(rep_list)
        if counter < rep_num:
#            rep_len = len(rep_list)
#            rep_product = [i ** (1/rep_len) for i in rep_product]
#            rep_product = normalizer(rep_product, scaler=1, integral=True)
            cond_list.append(rep_product)
        else:
            continue
    
    combined_prob = prob_sum(cond_list)

    return combined_prob


###############################################################################
## This function locates the positions of the local maxima in a list
def maxima_loc(samp_list, shift=0):
    '''
    Input is a list (representing probabilities). Output is a list of indicies
    where extremum (local maxima) are located, ranked by value. List of tuples
    of the form [(index, value), ...]. Can be shifted to appropriate region by 
    setting 'shift' equal to non-zero integer. 

    NOTE: I adjusted the inequalities (first one from '>' to '>=') so as to 
    pick up subsequent bases with identical probabilities, *BUT* only counts 
    the final one in the sequence.

    TODO: May want to incorporate some way of determining mu for regions of 
    uniform probability (i.e. flat profiles)
    '''
    
    maxima_indicies = [(i+1+shift, val) 
                       for i, val in enumerate(samp_list[1:-1]) 
                       if (samp_list[i+1] - samp_list[i]) >= 0
                       and (samp_list[i+2] - samp_list[i+1]) < 0]
    
    return maxima_indicies


###############################################################################
## This function extracts the (mu, sig) values from the tfit_dict for a given
# chr and region and outputs the list of tuples.
def mu_sig_extract(mu_list, width=1.0):
    '''
    This funciton just pulls the mu and sigma values out of the tfit_dict for
    a given chromesome and bed region. Returns tuples in list of form
    [(mu_1, sig_1), (mu_2, sig_2), ...].
    '''
    starts, stops, cov, samples = zip(*mu_list)
    mu_sig_list = [(round((i[1] + i[0]) / 2), ((i[1] - i[0]) / 2) * width)     # THIS FACTOR SAME AS ONE IN prob_list_generator()!!!
                   for i in zip(starts, stops)]

    return mu_sig_list


###############################################################################
## This function determins which of the newly identified mu positions to keep 
# and which to discard. At this point sigma is absent. The tuples are only 
# (mu_pos, mu_prob)
def mu_ranker(mus, num):
    '''
    This function  just takes the top 'num' based on highest probability 
    density values. At this point there is no sigma value. The tuples in list 
    'new_mu' should only be (mu_pos, mu_prob).
    '''
    prob_sorted_mu = sorted(mus, key=lambda x: x[1])
    rank_extracted_mu = prob_sorted_mu[-int(num):]
    final_sorted_mu = sorted(rank_extracted_mu, key=lambda x: x[0])

    return final_sorted_mu


###############################################################################
## This function finds the tfit mu-calls that are closest to each likelihood
# maxima located by maxima_loc(), and record the sigma for that tfit call,
# assigning it to the respective maxima.
def sigma_assigner(new_mu, old_mu_sig):
    '''
    This takes two lists of tuples, one containing mu locations and 
    probabilities (new_loc) and the other containing mu locations and sigmas
    (old_loc), and then assigns a sigma value for the new mu that's equal the
    distance weighted sum of all the sigmas for the old mu's
    '''
    new_pos, new_prob = zip(*new_mu)
    old_pos, old_sigs = zip(*old_mu_sig)

    new_sigs = []
    # Calculate distances between a new mu and all the old mu's, weight the
    # sum of the old sigmas by those distances, divide by total distance, to
    # calculate the sigma value for the new mu
    # NOTE!!! The 1 in (e[0] + 1) is to avoid dividing by zero. This might be
    # a problematic bias though.
    for mu in new_pos:
        dists = [abs(mu - old_mu) for old_mu in old_pos]
        new_sig = sum([e[1] / (e[0] + 1) for e in zip(dists, old_sigs)])
        total_weight = sum([1 / (e + 1) for e in dists])
        new_sig = new_sig / total_weight
        new_sigs.append(new_sig)
    
    new_mu_updated = [e for e in zip(new_pos, new_sigs, new_prob)]

    return new_mu_updated


###############################################################################
## This function resolves collisions between newly calculated bed intervals 
# (i.e. the new mu-sig). If two overlap, then the intervals are shrunk to 
# where the intervals touch.
def collision_resolver(mu_sig_list):
    '''
    Takes input list of (mu, sig, ...) tuples and evaluates if any of them are 
    overlapping. In the event they do, they are shrunk to the point that they 
    just touch. This is done in a L-to-R parse (so a doubly-overlapping region 
    may not end up directly adjacent to its lefthand neighbor). Scaling is 
    performed based on the relative lenghs of the two neighboring bed regions.
    '''
    # Make sure mu_sig_list is sorted by mu position
    mus = sorted(mu_sig_list, key=lambda x: x[0])

    for i, mu in enumerate(mus[:-1]):

        pos1 = mus[i][0]
        sig1 = mus[i][1]
        pos2 = mus[i+1][0]
        sig2 = mus[i+1][1]

        # Determine if mu_i and mu_i+1 overlap with one another
        if overlap_check((pos1-sig1, pos1+sig1), (pos2-sig2, pos2+sig2)):

            # Calculate distance and ratio of length between adjacent mu
            len_ratio = sig1 / (sig1 + sig2)
            dist = pos2 - pos1
            
            # Calculate new sigmas, and write them to mu list
            delta1 = round(dist * len_ratio)
            delta2 = round(dist * (1 - len_ratio))
            mus[i] = (pos1, delta1) + tuple(mus[i][2:])
            mus[i+1] = (pos2, delta2) + tuple(mus[i+1][2:])

        else:
            continue

    return mus


###############################################################################
## This function defines the boundaries of the bed region, using the updated
# sigmas (from sigma_assigner()) and outputs a list of strings formatted as 
# bedfile regions.
def bed_line_formatter(chromosome, mu_sig_list, width=1.0):
    '''
    Takes input list of new (mu, sigma) tuples and outputs list of strings 
    formatted as bedfile lines.
    '''
    bed_lines = []
    for mu in mu_sig_list:
        start = str(round(mu[0] - mu[1] / width))
        stop = str(round(mu[0] + mu[1] / width))
        bed_lines.append("\t".join([chromosome, start, stop]) + "\n")
#        avg = str(round((int(start) + int(stop)) / 2))
#        bed_lines.append("\t".join([chromosome, start, stop, avg]) + "\n")

    return bed_lines


###############################################################################
## MAIN
###############################################################################
def main():
    # Start timing
    start = time()

    ## Arg parse, define vars (bedfiles, sampids, groups), generate merged bed
    inputs = inputs_processor()  
    input_file = inputs['input']                                              # TEST!!!
    tfit_filenames = inputs['bedfiles']
    sampids = inputs['sampids']
    groupings = inputs['groupings']
    union_bedfile = inputs['merged']
    output_basename = inputs['output']
    verbose = inputs['verbose']
    weights = inputs['weights']
    width_ratio = inputs['width_ratio']
    remove_singletons = inputs['remove_singletons']

    num_samps = len(tfit_filenames)

    ## Define output files and open 'log' file 'miscall' files
    outbed_filename = output_basename + "_MUMERGE.bed"
    miscallfilename = output_basename + '_MISCALLS.bed'

    logfile = open(output_basename + '.log', 'w')
    miscallfile = open(miscallfilename, 'w')

    # Open singletons file
    if remove_singletons:
        singletonfilename = output_basename + '_SINGLETONS.bed'
        singletonfile = open(singletonfilename, 'w')

    ## Writes the initial, summary data in the miscalls and log files
    log_initializer(
        input_file,        
        tfit_filenames, 
        outbed_filename,
        union_bedfile, 
        miscallfilename, 
        output_basename,
        logfile, 
        miscallfile, 
        sampids, 
        groupings
    )

    if verbose:
        sys.stdout.write("\nGenerating 'bedtools merge' bedfile...\n")
    ## Load merged bedfile
    merge_regions = bedfile_reader(union_bedfile,
                                bedGraph=False,
                                print_header=False,
                                count=False)
    if verbose:
        sys.stdout.write("Building Tfit-regions dictionary...\n")
    ## Generate tfit dictionary, of form 
    # {'chr#': {(reg_start,reg_stop): [(mu_start,mu_stop,cov,'sampID'), ...]}}
    tfit_dict = mu_dict_generator(list(tfit_filenames),
                                merge_regions,
                                sampids = list(sampids),
                                verbose = verbose)

    # Count up the total number of regions (to be logged and printed out)
    total = 0
    for region_list in tfit_dict.values():
        total += len(region_list)
    logfile.write("\nTotal number of bedfile regions: {}\n".format(total))

    # Check to make sure no regions are empty, then generate distribution of 
    # tfit calls. Write to log file.
    call_num = []
    for chrome, region in tfit_dict.items():
        for interval, calls in region.items():
            call_num.append(len(calls))
    call_hist = Counter(call_num)
    del(call_num)
    logfile.write("\nDistribution of number of Tfit calls for a sample, "
        "within a region, across all samples (#calls: #instances):\n{}\n"
        .format(dict(call_hist)))

    # Region counter for verbose
    count = 1
    with open(outbed_filename, 'w') as output:
            
        ## Loop over regions in the tfit_dict (key1 = 'chr#', key2 = region)
        for chromosome in sorted(tfit_dict.keys()):
            for region in sorted(tfit_dict[chromosome].keys()):
                
                # Status counter and update at stdout
                if verbose:
                    sys.stdout.write("\rProcessed {} of {} regions"
                                    .format(count, total))
                    count += 1

                # Select Tfit calls for one region
                mu_list = tfit_dict[chromosome][region]
    #            print(chromosome, region, (region[0]+region[1])/2, mu_list)
                if call_remover(mu_list,remove_singletons):
                    # Write the singletons to a new output file
                    singletonfile.write("\n")
                    singletonfile.write("\t".join([str(chromosome), 
                                                str(region[0]), 
                                                str(region[1]), 
                                                str(mu_list[0][3])]))
    #                if verbose:
    #                    sys.stdout.write("\rskipping singleton...")
                    continue
                # Calculate average number of tfit calls per sample (rounds up)
                avg_num_mu = ceil(len(mu_list) / num_samps) + 1           # I'M JUST TESTING HOW THIS IMPACTS THE DELTA MU TEST (THE +1)

                # Generate prob dict (func of bp pos) for region of tfit calls
                sample_prob_dict = prob_list_formatter(region, 
                                                        mu_list, 
                                                        dist="normal",
                                                        width=width_ratio)     #CHECK!!!

                # Calculate combined prob array (function of base position),
                # from 'groups' and the probability lists in sample_prob_dict() 
                comb_prob = combined_prob_calculator(sample_prob_dict, 
                                                        groups=groupings)      #FIX!!!

                # Locate local maxima (shifted to range of 'region')
                potential_mu = maxima_loc(comb_prob, shift=region[0])          #CHECK!!!

                # Determine which updated mu locations to keep
                new_mu = mu_ranker(potential_mu, avg_num_mu)

                # If new_mu is empty, log in 'miscalls' and skip to next region
                if len(new_mu) == 0:
                    miscallfile.write("\n")
                    miscallfile.write("\t".join([str(chromosome), 
                                                str(region[0]), 
                                                str(region[1]), 
                                                str(mu_list)]))
                    continue

                # Extract (mu, sig) tuples for region from compiled tfit_dict
                old_mu_sig = mu_sig_extract(mu_list, width=width_ratio)
#               print(new_mu, "LEN(OLD):", len(old_mu_sig), chromosome, region)

                # Calculate updated sigma values for each updated mu location
                new_mu_sig = sigma_assigner(new_mu, old_mu_sig)

                # Address collisions between updated (mu, sig) in same region
                final_mu_sig = collision_resolver(new_mu_sig)                  #CHECK!!!

                # Convert final (mu, sig) to bed line format, write to output
                bedlines = bed_line_formatter(
                    chromosome, 
                    final_mu_sig, 
                    width=width_ratio
                )
                
                # Write updated bedlines to output file
                for line in bedlines:
                    output.write(line)

    sys.stdout.write("\n")
    end = time()

    logfile.write("\nRun time: {} sec\n".format(end - start))
    logfile.close()
    miscallfile.close()
    if remove_singletons:
        singletonfile.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
