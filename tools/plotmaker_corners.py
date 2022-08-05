import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import corner
import pickle, argparse
from healpy import Alm


def plotmaker(params, parameters, inj):

    '''
    Make posterior plots from the samples generated by the mcmc/nested sampling algorithm.

    Parameters
    -----------

    params : dictionary
        Dictionary of config params

    parameters: string
        Array or list of strings with names of the parameters

    inj : int
        Injection dict
    '''

    post = np.loadtxt(params['out_dir'] + "/post_samples.txt")


    ## setup the truevals dict
    truevals = []

    if params['modeltype']=='isgwb':

        truevals.append(inj['log_Np'])
        truevals.append( inj['log_Na'])
        truevals.append( inj['alpha'] )
        truevals.append( inj['ln_omega0'] )

    elif params['modeltype']=='noise_only':

        truevals.append(inj['log_Np'])
        truevals.append( inj['log_Na'])

    elif params['modeltype'] =='isgwb_only':

        truevals.append( inj['alpha'] )
        truevals.append( inj['ln_omega0'] )

    elif params['modeltype']=='sph_sgwb':

        truevals.append(inj['log_Np'])
        truevals.append( inj['log_Na'])
        truevals.append( inj['alpha'] )
        truevals.append( inj['ln_omega0'] )

        ## get blms
        for lval in range(1, params['lmax'] + 1):
            for mval in range(lval + 1):

                idx = Alm.getidx(params['lmax'], lval, mval)

                if mval == 0:
                    truevals.append(np.real(inj['blms'][idx]))
                else:
                    truevals.append(np.abs(inj['blms'][idx]))
                    truevals.append(np.angle(inj['blms'][idx]))




    if len(truevals) > 0:
        knowTrue = 1 ## Bit for whether we know the true vals or not
    else:
        knowTrue = 0


    npar = len(parameters)

    plotrange = [0.999]*npar

    if params['out_dir'][-1] != '/':
        params['out_dir'] = params['out_dir'] + '/'

    ## Make corner plots
    fig = corner.corner(post, range=plotrange, labels=parameters, quantiles=(0.16, 0.84),
                        smooth=None, smooth1d=None, show_titles=True,
                        title_kwargs={"fontsize": 12},label_kwargs={"fontsize": 14},
                        fill_contours=True, use_math_text=True, )


    # Put correct values
    # Extract the axes
    axes = np.array(fig.axes).reshape((npar, npar))
    for ii in range(npar):
        ax = axes[ii, ii]

        ## Draw truevals if they exist
        if knowTrue:
            ax.axvline(truevals[ii], color="g", label='true value')

    ## Save posterior
    plt.savefig(params['out_dir'] + 'corners.png', dpi=150)
    print("Posteriors plots printed in " + params['out_dir'] + "corners.png")
    plt.close()

if __name__ == '__main__':

    # Create parser
    parser = argparse.ArgumentParser(prog='plotmaker', usage='%(prog)s [options] rundir', description='run plotmaker')

    # Add arguments
    parser.add_argument('rundir', metavar='rundir', type=str, help='The path to the run directory')

    # execute parser
    args = parser.parse_args()


    paramfile = open(args.rundir + '/config.picle')

    ## things are loaded from the pickle file in the same order they are put in
    params = pickle.load(paramfile)
    inj = pickle.load(paramfile)
    parameters = pickle.load(paramfile)

    plotmaker(params, parameters, inj)
