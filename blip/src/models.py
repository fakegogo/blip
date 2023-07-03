import numpy as np
from matplotlib import pyplot as plt
from scipy.interpolate import interp1d
import healpy as hp
from blip.src.geometry import geometry
from blip.src.sph_geometry import sph_geometry
from blip.src.clebschGordan import clebschGordan
from blip.src.astro import Population
from blip.src.instrNoise import instrNoise
import blip.src.astro as astro



class submodel(geometry,sph_geometry,clebschGordan,instrNoise):
    '''
    Modular class that can represent either an injection or an analysis model. Will have different attributes depending on use case.
    
    Includes all information required to generate an injection or a likelihood/prior.
    
    New models (injection or analysis) should be added here.
    
    '''
    def __init__(self,params,inj,submodel_name,fs,f0,tsegmid,injection=False,suffix=''):
        '''
        Each submodel should be defined as "[spectral]_[spatial]", save for the noise model, which is just "noise".
        
        e.g., "powerlaw_isgwb" defines a submodel with an isotropic spatial distribution and a power law spectrum.
        
        Resulting objects has different attributes depending on if it is to be used as an Injection component or part of our unified multi-signal Model.
        
        Arguments
        ------------
        params, inj (dict)  : params and inj config dictionaries as generated in run_blip.py
        submodel_name (str) : submodel name, defined as "[spectral]_[spatial]" (or just "noise")
        fs, f0 (array)      : frequency array and its LISA-characteristic-frequency-scaled counterpart (f0=fs/(2*fstar))
        tsegmid (array)     : array of time segment midpoints
        injection (bool)    : If True, generate the submodel as an injection component, rather than a Model submodel.
        suffix (str)        : String to append to parameter names, etc., to differentiate between duplicate submodels.
        
        Returns
        ------------
        submodel (object) : submodel with all needed attributes to serve as an Injection component or Model submodel as desired.
        
        '''
        
        ## preliminaries
        self.params = params
        self.inj = inj
        self.armlength = 2.5e9 ## armlength in meters
        self.fs = fs
        self.f0= f0
        self.time_dim = tsegmid.size
        self.name = submodel_name
        self.injection = injection
        geometry.__init__(self)
        
        
        
        if injection:
            self.truevals = {}
        
        ## plot kwargs dict to allow for case-by-case exceptions to our usual plotting approach
        ## e.g., the population spectra look real weird as dotted lines.
        self.plot_kwargs = {}
            
        ## handle & return noise case in bespoke fashion, as it is quite different from the signal models
        if submodel_name == 'noise':
            self.spectral_parameters = [r'$\log_{10} (Np)$'+suffix, r'$\log_{10} (Na)$'+suffix]
            self.spatial_parameters = []
            self.parameters = self.spectral_parameters
            self.Npar = 2
            ## for plotting
            self.fancyname = "Instrumental Noise"
            self.color = 'dimgrey'
            self.has_map = False
            # Figure out which instrumental noise spectra to use
            if self.params['tdi_lev']=='aet':
                self.instr_noise_spectrum = self.aet_noise_spectrum
                if injection:
                    self.gen_noise_spectrum = self.gen_aet_noise
            elif self.params['tdi_lev']=='xyz':
                self.instr_noise_spectrum = self.xyz_noise_spectrum
                if injection:
                    self.gen_noise_spectrum = self.gen_xyz_noise
            elif self.params['tdi_lev']=='michelson':
                self.instr_noise_spectrum = self.mich_noise_spectrum
                if injection:
                    self.gen_noise_spectrum = self.gen_michelson_noise
            else:
                raise ValueError("Unknown specification of 'tdi_lev'; can be 'michelson', 'xyz', or 'aet'.")
            if not injection:
                ## prior transform
                self.prior = self.instr_noise_prior
                ## covariance calculation
                self.cov = self.compute_cov_noise
            else:
                ## truevals
                self.truevals[r'$\log_{10} (Np)$'] = self.inj['log_Np']
                self.truevals[r'$\log_{10} (Na)$'] = self.inj['log_Na']
                ## save the frozen noise spectra
                self.frozen_spectra = self.instr_noise_spectrum(self.fs,self.f0,Np=10**self.inj['log_Np'],Na=10**self.inj['log_Na'])
            
            return

        else:
            self.parameters = []
            self.spectral_parameters = []
            self.spatial_parameters = []
            ## for convenience, so there's no need to specify e.g., "population_population"
            if submodel_name == 'population':
                self.spectral_model_name = self.spatial_model_name = submodel_name
            else:
                self.spectral_model_name, self.spatial_model_name = submodel_name.split('_')
            
            
        
        ###################################################
        ###            BUILD NEW MODELS HERE            ###
        ###################################################

        ## assignment of spectrum
        if self.spectral_model_name == 'powerlaw':
            self.spectral_parameters = self.spectral_parameters + [r'$\alpha$', r'$\log_{10} (\Omega_0)$']
            self.omegaf = self.powerlaw_spectrum
            self.fancyname = "Power Law SGWB"
            if not injection:
                self.spectral_prior = self.powerlaw_prior
            else:
                self.truevals[r'$\alpha$'] = self.inj['alpha']
                self.truevals[r'$\log_{10} (\Omega_0)$'] = self.inj['log_omega0']
        elif self.spectral_model_name == 'brokenpowerlaw':
            self.spectral_parameters = self.spectral_parameters + [r'$\alpha_1$',r'$\log_{10} (\Omega_0)$',r'$\alpha_2$',r'$\log_{10} (f_{break})$']
            self.omegaf = self.broken_powerlaw_spectrum
            self.fancyname = "Broken Power Law SGWB"
            if not injection:
                self.spectral_prior = self.broken_powerlaw_prior
            else:
                self.truevals[r'$\alpha_1$'] = self.inj['alpha1']
                self.truevals[r'$\log_{10} (\Omega_0)$'] = self.inj['log_omega0']
                self.truevals[r'$\alpha_2$'] = self.inj['alpha2']
                self.truevals[r'$\log_{10} (f_{break})$'] = self.inj['log_fbreak']
        
        elif self.spectral_model_name == 'truncatedpowerlaw':
            self.spectral_parameters = self.spectral_parameters + [r'$\alpha$', r'$\log_{10} (\Omega_0)$', r'$\log_{10} (f_{\mathrm{cut}})$',r'$\log_{10} (f_{\mathrm{scale}})$']
            self.omegaf = self.truncated_powerlaw_spectrum
            self.fancyname = "Truncated Power Law SGWB"
            if not injection:
                self.spectral_prior = self.truncated_powerlaw_prior
            else:
                self.truevals[r'$\alpha$'] = self.inj['alpha']
                self.truevals[r'$\log_{10} (\Omega_0)$'] = self.inj['log_omega0']
                self.truevals[r'$\log_{10} (f_{\mathrm{cut}})$'] = self.inj['log_fcut']
                self.truevals[r'$\log_{10} (f_{\mathrm{scale}})$'] = self.inj['log_fscale']
        elif self.spectral_model_name == 'population':
            if not injection:
                raise ValueError("Populations are injection-only.")
            self.fancyname = "DWD Population"
            self.population = Population(self.params,self.inj,self.fs)
            self.compute_Sgw = self.population.Sgw_wrapper
            self.omegaf = self.population.omegaf_wrapper
            self.ispop = True
            self.plot_kwargs |= {'ls':'-','lw':0.75,'alpha':0.6}
        
        else:
            ValueError("Unsupported spectrum type. Check your spelling or add a new spectrum model!")
        
        ## assignment of response and spatial methods
        response_kwargs = {}
        
        ## This is the isotropic spatial model, and has no additional parameters.
        if self.spatial_model_name == 'isgwb':
            if self.params['tdi_lev'] == 'michelson':
                self.response = self.isgwb_mich_response
            elif self.params['tdi_lev'] == 'xyz':
                self.response = self.isgwb_xyz_response
            elif self.params['tdi_lev'] == 'aet':
                self.response = self.isgwb_aet_response
            else:
                raise ValueError("Invalid specification of tdi_lev. Can be 'michelson', 'xyz', or 'aet'.")
            
            ## compute response matrix
            self.response_mat = self.response(f0,tsegmid,**response_kwargs)
            
            ## plotting stuff
            self.fancyname = "Isotropic "+self.fancyname
            self.subscript = "_{\mathrm{I}}"
            self.color='darkorange'
            self.has_map = False

            if not injection:
                ## prior transform
                self.prior = self.isotropic_prior
                self.cov = self.compute_cov_isgwb
            else:
                ## create a wrapper b/c isotropic and anisotropic injection responses are different
                self.inj_response_mat = self.response_mat
        
        ## This is the spherical harmonic spatial model. It is the workhorse of the spherical harmonic anisotropic analysis.
        ## It can also be used to perform arbitrary injections in the spherical harmonic basis via direct specification of the blms.
        elif self.spatial_model_name == 'sph':
            
            if injection:
                self.lmax = self.inj['inj_lmax']
            else:
                self.lmax = self.params['lmax']
            
            ## almax is twice the blmax
            self.almax = 2*self.lmax
            response_kwargs['set_almax'] = self.almax
            
            if self.params['tdi_lev']=='michelson':
                self.response = self.asgwb_mich_response
            elif self.params['tdi_lev']=='xyz':
                self.response = self.asgwb_xyz_response
            elif self.params['tdi_lev']=='aet':
                self.response = self.asgwb_aet_response
            else:
                raise ValueError("Invalid specification of tdi_lev. Can be 'michelson', 'xyz', or 'aet'.")
            
            ## compute response matrix
            self.response_mat = self.response(f0,tsegmid,**response_kwargs)
            
            ## plotting stuff
            self.fancyname = "Anisotropic "+self.fancyname
            self.subscript = "_{\mathrm{A}}"
            self.color = 'teal'
            self.has_map = True
            
            # add the blms
            blm_parameters = gen_blm_parameters(self.lmax)
            
            ## save the blm start index for the prior, then add the blms to the parameter list
            self.blm_start = len(self.spectral_parameters)
            self.spatial_parameters = self.spatial_parameters + blm_parameters
            
            if not injection:
                self.prior = self.sph_prior
                self.cov = self.compute_cov_asgwb
            else:
                ## get blm truevals
                val_list = self.blms_2_blm_params(inj['blms'])
                
                for param, val in zip(blm_parameters,val_list):
                    self.truevals[param] = val
                
                ## get alms
                self.alms_inj = self.blm_2_alm(np.array(inj['blms']))
                ## get sph basis skymap
                self.sph_skymap =  hp.alm2map(self.alms_inj[0:hp.Alm.getsize(self.almax)],self.params['nside'])
                ## get response integrated over the Ylms
                self.summ_response_mat = self.compute_summed_response(self.alms_inj)
                ## create a wrapper b/c isotropic and anisotropic injection responses are different
                self.inj_response_mat = self.summ_response_mat
        
        ## Handle all the astrophysical spatial distributions together due to their similarities
        elif self.spatial_model_name in ['galaxy','dwarfgalaxy','lmc','pointsource','twopoints','population']:
            
            ## the astrophysical spatial models are generally injection-only
            if not injection:
                raise ValueError("This model is injection-only.")
            
            self.has_map = True
            
            ## almax is twice the blmax
            self.lmax = self.inj['inj_lmax']
            self.almax = 2*self.lmax
            response_kwargs['set_almax'] = self.almax
            
            if self.params['tdi_lev']=='michelson':
                self.response = self.asgwb_mich_response
            elif self.params['tdi_lev']=='xyz':
                self.response = self.asgwb_xyz_response
            elif self.params['tdi_lev']=='aet':
                self.response = self.asgwb_aet_response
            else:
                raise ValueError("Invalid specification of tdi_lev. Can be 'michelson', 'xyz', or 'aet'.")
            
            ## compute response matrix
            self.response_mat = self.response(f0,tsegmid,**response_kwargs)
            
            ## model-specific quantities
            if self.spatial_model_name == 'galaxy':
                ## store the high-level MW truevals for the hierarchical analysis
                self.truevals[r'$r_{\mathrm{h}}$'] = inj['rh']
                self.truevals[r'$z_{\mathrm{h}}$'] = inj['zh']
                ## plotting stuff
                self.fancyname = "Galactic Foreground"
                self.subscript = "_{\mathrm{G}}"
                self.color = 'mediumorchid'
                ## generate skymap
                self.skymap = astro.generate_galactic_foreground(self.inj['rh'],self.inj['zh'],self.params['nside'])
            elif self.spatial_model_name == 'lmc':
                ## plotting stuff
                self.fancyname = "LMC"
                self.subscript = "_{\mathrm{LMC}}"
                self.color = 'darkmagenta'
                ## generate skymap
                self.skymap = astro.generate_sdg(self.params['nside']) ## sdg defaults are for the LMC
            elif self.spatial_model_name == 'dwarfgalaxy':
                ## plotting stuff
                self.fancyname = "Dwarf Galaxy"
                self.subscript = "_{\mathrm{DG}}"
                self.color = 'maroon'
                ## generate skymap
                self.skymap = astro.generate_sdg(self.params['nside'],ra=self.inj['sdg_RA'], dec=self.inj['sdg_DEC'], D=self.inj['sdg_dist'], r=self.inj['sdg_rad'], N=self.inj['sdg_N'])
            elif self.spatial_model_name == 'pointsource':
                ## plotting stuff
                self.fancyname = "Point Source"
                self.subscript = "_{\mathrm{1P}}"
                self.color = 'forestgreen'
                ## generate skymap
                self.skymap = astro.generate_point_source(self.inj['theta'],self.inj['phi'],self.params['nside'])
            elif self.spatial_model_name == 'twopoints':
                ## revisit this when I have duplicates sorted, maybe unnecessary (could just have 2x point source injection components)
                ## plotting stuff
                self.fancyname = "Two Point Sources"
                self.subscript = "_{\mathrm{2P}}"
                self.color = 'gold'
                ## generate skymap
                self.skymap = astro.generate_two_point_source(self.inj['theta_1'],self.inj['phi_1'],self.inj['theta_2'],self.inj['phi_2'],self.params['nside'])
            elif self.spatial_model_name == 'population':
                ## flag the fact that we have a population skymap
                self.skypop = True
                ## plotting stuff
                self.fancyname = "DWD Population"
                self.subscript = "_{\mathrm{P}}"
                self.color = 'midnightblue'
                if self.spectral_model_name != 'population':
                    ## generate population if still needed
                    self.population = Population(self.params,self.inj,self.fs)
                self.skymap = self.population.skymap
            
            else:
                raise ValueError("Astrophysical submodel type not found. Did you add a new model to the list at the top of this section?")
            
            self.process_astro_skymap(self.skymap)
            

        elif self.spatial_model_name == 'hierarchical':
            pass
        else:
            raise ValueError("Invalid specification of spatial model name ('{}'). Can be 'isgwb', 'sph', 'galaxy', or 'hierarchical'.".format(self.spatial_model_name))
        
        
        ## store final parameter list and count
        self.parameters = self.parameters + self.spectral_parameters + self.spatial_parameters
        if not injection:               
            self.Npar = len(self.parameters)
        ## store response kwargs for use elsewhere as needed
        self.response_kwargs = response_kwargs
        ## add suffix to parameter names and trueval keys, if desired
        ## (we need this in the multi-model or duplicate model case)
        if suffix != '':
            if injection:
                updated_truevals = {parameter+suffix:self.truevals[parameter] for parameter in self.parameters}
                self.truevals = updated_truevals
            updated_spectral_parameters = [parameter+suffix for parameter in self.spectral_parameters]
            updated_spatial_parameters = [parameter+suffix for parameter in self.spatial_parameters]
            updated_parameters = updated_spectral_parameters+updated_spatial_parameters
            if len(updated_parameters) != len(self.parameters):
                raise ValueError("If you've added a new variety of parameters above, you'll need to update this bit of code too!")
            self.spectral_parameters = updated_spectral_parameters
            self.spatial_parameters = updated_spatial_parameters
            self.parameters = updated_parameters
            
        
        return
    

    #############################
    ##    Spectral Functions   ##
    #############################
    def powerlaw_spectrum(self,fs,alpha,log_omega0):
        '''
        Function to calculate a simple power law spectrum.
        
        Arguments
        -----------
        fs (array of floats) : frequencies at which to evaluate the spectrum
        alpha (float)        : slope of the power law
        log_omega0 (float)   : power law amplitude in units of log dimensionless GW energy density at f_ref
        
        Returns
        -----------
        spectrum (array of floats) : the resulting power law spectrum
        
        '''
        return 10**(log_omega0)*(fs/self.params['fref'])**alpha
    
    
    def broken_powerlaw_spectrum(self,fs,alpha_1,log_omega0,alpha_2,log_fbreak):
        '''
        Function to calculate a broken power law spectrum.
        
        Arguments
        -----------
        fs (array of floats) : frequencies at which to evaluate the spectrum
        alpha_1 (float)      : slope of the first power law
        log_omega0 (float)   : power law amplitude of the first power law in units of log dimensionless GW energy density at f_ref
        alpha_2 (float)      : slope of the second power law
        log_fbreak (float)   : log of the break frequency ("knee") in Hz
        
        Returns
        -----------
        spectrum (array of floats) : the resulting broken power law spectrum
        
        '''
        delta = 0.1
        fbreak = 10**log_fbreak
        norm = (fbreak/self.params['fref'])**alpha_1 / 1.25989194 ## this normalizes the broken powerlaw such that its first leg matches the equivalent standard power law
        return norm * (10**log_omega0)*(fs/fbreak)**(alpha_1) * (0.5*(1+(fs/fbreak)**(1/delta)))**((alpha_1-alpha_2)*delta)
    
    def truncated_powerlaw_spectrum(self,fs,alpha,log_omega0,log_fcut,log_fscale):
        '''
        Function to calculate a tanh-truncated power law spectrum.
        
        Arguments
        -----------
        fs (array of floats) : frequencies at which to evaluate the spectrum
        alpha (float)        : slope of the power law
        log_omega0 (float)   : power law amplitude of the power law in units of log dimensionless GW energy density at f_ref (if left un-truncated)
        log_fcut (float)     : log of the cut frequency ("knee") in Hz
        log_fscale           : log of the cutoff scale factor in Hz
        
        Returns
        -----------
        spectrum (array of floats) : the resulting truncated power law spectrum
        
        '''
        fcut = 10**log_fcut
        fscale = 10**log_fscale
        return 0.5 * (10**log_omega0)*(fs/self.params['fref'])**(alpha) * (1+np.tanh((fcut-fs)/fscale))
    
    def compute_Sgw(self,fs,omegaf_args):
        '''
        Wrapper function to generically calculate the associated stochastic gravitational wave PSD (S_gw)
            for a spectral model given in terms of the dimensionless GW energy density Omega(f)
        
        Arguments
        -----------
        fs (array of floats) : frequencies at which to evaluate the spectrum
        omegaf_args (list)   : list of arguments for the relevant Omega(f) function
        
        Returns
        -----------
        Sgw (array of floats) : the resulting GW PSD
        
        '''
        H0 = 2.2*10**(-18)
        Omegaf = self.omegaf(fs,*omegaf_args)
        Sgw = Omegaf*(3/(4*fs**3))*(H0/np.pi)**2
        return Sgw
    
    #############################
    ##          Priors         ##
    #############################
    def isotropic_prior(self,theta):
        '''
        Isotropic prior transform. Just serves as a wrapper for the spectral prior, as no additional foofaraw is necessary.
        
        Arguments
        -----------

        theta   : float
            A list or numpy array containing samples from a unit cube.

        Returns
        ---------

        theta   :   float
            theta with each element rescaled for the spectral parameters.
            
        '''
        return self.spectral_prior(theta)
    
    def sph_prior(self,theta):
        '''
        Spherical harmonic anisotropic prior transform. Combines a generic spectral prior function with the spherical harmonic priors for the desired lmax.
        
        Arguments
        -----------

        theta   : float
            A list or numpy array containing samples from a unit cube.

        Returns
        ---------

        theta   :   float
            theta with each element rescaled for both the spectral and spatial parameters.
        '''
        
        ## spectral prior takes everything up to 
        spectral_theta = self.spectral_prior(theta[:self.blm_start])
        
        # Calculate lmax from the size of theta blm arrays. The shape is
        # given by size = (lmax + 1)**2 - 1. The '-1' is because b00 is
        # an independent parameter
        lmax = np.sqrt( len(theta[self.blm_start:]) + 1 ) - 1

        if lmax.is_integer():
            lmax = int(lmax)
        else:
            raise ValueError('Illegitimate theta size passed to the spherical harmonic prior')

        # The rest of the priors define the blm parameter space
        sph_theta = []

        ## counter for the rest of theta
        cnt = self.blm_start

        for lval in range(1, lmax + 1):
            for mval in range(lval + 1):

                if mval == 0:
                    sph_theta.append(6*theta[cnt] - 3)
                    cnt = cnt + 1
                else:
                    ## prior on amplitude, phase
                    sph_theta.append(3* theta[cnt])
                    sph_theta.append(2*np.pi*theta[cnt+1] - np.pi)
                    cnt = cnt + 2

        return spectral_theta+sph_theta
    
    def hierarchical_prior(self,theta):
        '''
        Hierarchical anisotropic prior transform. Combines a generic spectral prior function with the hierarchical astrophysical prior.
        
        Arguments
        -----------

        theta   : float
            A list or numpy array containing samples from a unit cube.

        Returns
        ---------

        theta   :   float
            theta with each element rescaled for both the spectral and spatial parameters.
        '''
        pass
        
        
    def instr_noise_prior(self,theta):


        '''
        Prior function for only instrumental noise

        Parameters
        -----------

        theta   : float
            A list or numpy array containing samples from a unit cube.

        Returns
        ---------

        theta   :   float
            theta with each element rescaled. The elements are  interpreted as alpha, omega_ref, Np and Na

        '''


        # Unpack: Theta is defined in the unit cube
        log_Np, log_Na = theta

        # Transform to actual priors
        log_Np = -5*log_Np - 39
        log_Na = -5*log_Na - 46

        return [log_Np, log_Na]
    
    def powerlaw_prior(self,theta):


        '''
        Prior function for an isotropic stochastic backgound analysis.

        Parameters
        -----------

        theta   : float
            A list or numpy array containing samples from a unit cube.

        Returns
        ---------

        theta   :   float
            theta with each element rescaled. The elements are  interpreted as alpha and log(Omega0)

        '''


        # Unpack: Theta is defined in the unit cube
        # Transform to actual priors
        alpha       =  10*theta[0]-5
        log_omega0  = -10*theta[1] - 4
        
        return [alpha, log_omega0]
    
    def broken_powerlaw_prior(self,theta):


        '''
        Prior function for a stochastic signal search with a broken power law spectral model.

        Parameters
        -----------

        theta   : float
            A list or numpy array containing samples from a unit cube.

        Returns
        ---------

        theta   :   float
            theta with each element rescaled. The elements are  interpreted as alpha_1, log(Omega_0), alpha_2, and log(f_break).

        '''

        # Unpack: Theta is defined in the unit cube
        # Transform to actual priors
        alpha_1 = 10*theta[0] - 4
        log_omega0 = -10*theta[1] - 4
        alpha_2 = 40*theta[2]
        log_fbreak = -2*theta[3] - 2

        return [alpha_1, log_omega0, alpha_2, log_fbreak]
    
    def truncated_powerlaw_prior(self,theta):


        '''
        Prior function for a stochastic signal search with a truncated power law spectral model.

        Parameters
        -----------

        theta   : float
            A list or numpy array containing samples from a unit cube.

        Returns
        ---------

        theta   :   float
            theta with each element rescaled. The elements are  interpreted as alpha, log(Omega_0), log(f_cut), and log(f_scale)

        '''

        # Unpack: Theta is defined in the unit cube
        # Transform to actual priors
        alpha = 10*theta[0] - 5
        log_omega0 = -10*theta[1] - 4
        log_fcut = -2*theta[2] - 2
        log_fscale = -2*theta[3] - 2
        

        return [alpha, log_omega0, log_fcut, log_fscale]
    
    
    
    
    
    
    #############################
    ## Covariance Calculations ##
    #############################
    def compute_cov_noise(self,theta):
        '''
        Computes the noise covariance for a given draw of log_Np, log_Na
        
        Arguments
        ----------
        theta (float)   :  A list or numpy array containing samples from a unit cube.
        
        Returns
        ----------
        cov_noise (array) : The corresponding 3 x 3 x frequency x time covariance matrix for the detector noise submodel.
        
        '''
        ## unpack priors
        log_Np, log_Na = theta

        Np, Na =  10**(log_Np), 10**(log_Na)

        ## Modelled Noise PSD
        cov_noise = self.instr_noise_spectrum(self.fs,self.f0, Np, Na)

        ## repeat C_Noise to have the same time-dimension as everything else
        cov_noise = np.repeat(cov_noise[:, :, :, np.newaxis], self.time_dim, axis=3)
        
        return cov_noise
    
    def compute_cov_isgwb(self,theta):
        '''
        Computes the covariance matrix contribution from a generic isotropic stochastic GW signal.
        
        Arguments
        ----------
        theta (float)   :  A list or numpy array containing samples from a unit cube.
        
        Returns
        ----------
        cov_sgwb (array) : The corresponding 3 x 3 x frequency x time covariance matrix for an isotropic SGWB submodel.
        
        '''
        ## Signal PSD
        Sgw = self.compute_Sgw(self.fs,theta)

        ## The noise spectrum of the GW signal. Written down here as a full
        ## covariance matrix axross all the channels.
        cov_sgwb = Sgw[None, None, :, None]*self.response_mat
        
        return cov_sgwb
    
    def compute_cov_asgwb(self,theta):
        '''
        Computes the covariance matrix contribution from a generic anisotropic stochastic GW signal.
        
        Arguments
        ----------
        theta (float)   :  A list or numpy array containing samples from a unit cube.
        
        Returns
        ----------
        cov_sgwb (array) : The corresponding 3 x 3 x frequency x time covariance matrix for an anisotropic SGWB submodel.
        
        '''
        ## Signal PSD
        Sgw = self.compute_Sgw(self.fs,theta[:self.blm_start])
        
        ## get skymap and integrate over alms
        summ_response_mat = self.compute_summed_response(self.compute_skymap_alms(theta[self.blm_start:]))

        ## The noise spectrum of the GW signal. Written down here as a full
        ## covariance matrix axross all the channels.
        cov_sgwb = Sgw[None, None, :, None]*summ_response_mat
        
        return cov_sgwb

       
    #############################
    ##   Skymap Calculations   ##
    #############################
    
    def compute_skymap_alms(self,blm_params):
        '''
        Function to compute the anisotropic skymap a_lms from the blm parameters.
        
        Arguments
        ----------
        blm_params (array of complex floats) : the blm parameters
        
        Returns
        ----------
        alm_vals (array of complex floats) : the corresponding alms
        
        '''
        ## Spatial distribution
        blm_vals = self.blm_params_2_blms(blm_params)
        alm_vals = self.blm_2_alm(blm_vals)

        ## normalize and return
        return alm_vals/(alm_vals[0] * np.sqrt(4*np.pi))
    
    def compute_summed_response(self,alms):
        '''
        Function to compute the integrated, skymap-convolved anisotropic response
        
        Arguments
        ----------
        alms (array of complex floats) : the spherical harmonic alms
        
        Returns
        ----------
        summ_response_mat (array) : the sky/alm-integrated response (3 x 3 x frequency x time)
        
        '''
        return np.einsum('ijklm,m', self.response_mat, alms)
    
    def process_astro_skymap(self,skymap):
        '''
        
        Function that takes in an astrophysical pixel skymap and:
            - calculates all associated sph quantities
            - computes corresponding blm parameter truevals
            - convolves with response
            
        Arguments
        -----------
        skymap (healpy array) : pixel-basis astrophysical skymap
        
        '''
        ## transform to blms
        self.astro_blms = astro.skymap_pix2sph(skymap,self.lmax)
        ## get corresponding truevals
        inj_blms = self.blms_2_blm_params(self.astro_blms)
        blm_parameters = gen_blm_parameters(self.lmax)
        for param, val in zip(blm_parameters,inj_blms):
            self.truevals[param] = val
        
        self.alms_inj = self.blm_2_alm(self.astro_blms)
        self.alms_inj = self.alms_inj/(self.alms_inj[0] * np.sqrt(4*np.pi))
        self.sph_skymap = hp.alm2map(self.alms_inj[0:hp.Alm.getsize(self.almax)],self.params['nside'])
        ## get response integrated over the Ylms
        self.summ_response_mat = self.compute_summed_response(self.alms_inj)
        ## create a wrapper b/c isotropic and anisotropic injection responses are different
        self.inj_response_mat = self.summ_response_mat
        
        return




###################################################
###      UNIFIED MODEL PRIOR & LIKELIHOOD       ###
###################################################


class Model():
    '''
    Class to house all model attributes in a modular fashion.
    '''
    def __init__(self,params,inj,fs,f0,tsegmid,rmat):
        
        '''
        Model() parses a Model string from the params file. This is of the form of an arbitrary number of "+"-delimited submodel types.
        Each submodel should be defined as "[spectral]_[spatial]", save for the noise model, which is just "noise".
        
        e.g., "noise+powerlaw_isgwb+truncated-powerlaw_sph" defines a model with noise, an isotropic SGWB with a power law spectrum,
            and a (spherical harmonic model for) an anisotropic SGWB with a truncated power law spectrum.
        
        Arguments
        ------------
        params, inj (dict)  : params and inj config dictionaries as generated in run_blip.py
        fs, f0 (array)      : frequency array and its LISA-characteristic-frequency-scaled counterpart (f0=fs/(2*fstar))
        tsegmid (array)     : array of time segment midpoints
        rmat (array)        : the data correllation matrix for all LISA arms
        
        Returns
        ------------
        Model (object) : Unified Model comprised of an arbitrary number of noise/signal submodels, with a corresponding unified prior and likelihood.
        
        '''
        
        self.fs = fs
        self.params = params
        
        ## separate into submodels
        self.submodel_names = params['model'].split('+')
        
        ## separate into submodels
        base_component_names = params['model'].split('+')
        
        ## check for and differentiate duplicate injections
        ## this will append 1 (then 2, then 3, etc.) to any duplicate submodel names
        ## we will also generate appropriate variable suffixes to use in plots, etc..
        self.submodel_names = catch_duplicates(base_component_names)
        suffixes = gen_suffixes(base_component_names)
        
        ## initialize submodels
        self.submodels = {}
        self.Npar = 0
        self.parameters = {}
        all_parameters = []
        spectral_parameters = []
        spatial_parameters = []
        for submodel_name, suffix in zip(self.submodel_names,suffixes):
            sm = submodel(params,inj,submodel_name,fs,f0,tsegmid,suffix=suffix)
            self.submodels[submodel_name] = sm
            self.Npar += sm.Npar
            self.parameters[submodel_name] = sm.parameters
            spectral_parameters += sm.spectral_parameters
            spatial_parameters += sm.spatial_parameters
            all_parameters += sm.parameters
        self.parameters['spectral'] = spectral_parameters
        self.parameters['spatial'] = spatial_parameters
        self.parameters['all'] = all_parameters
        
        ## assign reference to data for use in likelihood
        self.rmat = rmat
        

    

    def prior(self,unit_theta):
        '''
        Unified prior function to interatively perform prior draws for each submodel in the proper order
        
        Arguments
        ----------------
        unit_theta (array) : draws from the unit cube
        
        Returns
        ----------------
        theta (list) : transformed prior draws for all submodels in sequence
        '''
        theta = []
        start_idx = 0
        
        for sm_name in self.submodel_names:
            sm = self.submodels[sm_name]
            theta += sm.prior(unit_theta[start_idx:(start_idx+sm.Npar)])
            start_idx += sm.Npar
        
        if len(theta) != len(unit_theta):
            raise ValueError("Input theta does not have same length as output theta, something has gone wrong!")
        
        return theta
    
    
    def likelihood(self,theta):
        '''
        Unified likelihood function to compare the combined covariance contributions of a generic set of noise/SGWB models to the data.
        
        Arguments
        ----------------
        theta (list) : transformed prior draws for all submodels in sequence
        
        Returns
        ----------------
        loglike (float) : resulting joint log likelihood
        '''
        start_idx = 0
        for i, sm_name in enumerate(self.submodel_names):
            sm = self.submodels[sm_name]
            theta_i = theta[start_idx:(start_idx+sm.Npar)]
            start_idx += sm.Npar
            if i==0:
                cov_mat = sm.cov(theta_i)
            else:
                cov_mat = cov_mat + sm.cov(theta_i)

        ## change axis order to make taking an inverse easier
        cov_mat = np.moveaxis(cov_mat, [-2, -1], [0, 1])

        ## take inverse and determinant
        inv_cov, det_cov = bespoke_inv(cov_mat)

        logL = -np.einsum('ijkl,ijkl', inv_cov, self.rmat) - np.einsum('ij->', np.log(np.pi * self.params['seglen'] * np.abs(det_cov)))


        loglike = np.real(logL)

        return loglike
    

###################################################
###       UNIFIED INJECTION INFRASTRUCTURE      ###
################################################### 

    
class Injection():#geometry,sph_geometry):
    '''
    Class to house all injection attributes in a modular fashion.
    '''
    def __init__(self,params,inj,fs,f0,tsegmid):
        '''
        Injection() parses a Injection string from the params file. This is of the form of an arbitrary number of "+"-delimited submodel types.
        Each submodel should be defined as "[spectral]_[spatial]", save for the noise model, which is just "noise".
        
        e.g., "noise+powerlaw_isgwb+truncated-powerlaw_sph" defines an injection with noise, an isotropic SGWB with a power law spectrum,
            and a (spherical harmonic description of) an anisotropic SGWB with a truncated power law spectrum.
        
        Arguments
        ------------
        params, inj (dict)  : params and inj config dictionaries as generated in run_blip.py
        fs, f0 (array)      : frequency array and its LISA-characteristic-frequency-scaled counterpart (f0=fs/(2*fstar))
        tsegmid (array)     : array of time segment midpoints
        
        Returns
        ------------
        Injection (object)  : Unified Injection comprised of an arbitrary number of noise/signal injection components, with a variety of helper functions to aid in the BLIP injection procedure.
        
        '''
        self.params = params
        self.inj = inj
        
        self.frange = fs
        self.f0 = f0
        self.tsegmid = tsegmid
        
        ## separate into components
        base_component_names = inj['injection'].split('+')
        
        ## check for and differentiate duplicate injections
        ## this will append 1 (then 2, then 3, etc.) to any duplicate component names
        ## we will also generate appropriate variable suffixes to use in plots, etc..
        self.component_names = catch_duplicates(base_component_names)
        ## it's useful to have a version of this without the detector noise
        self.sgwb_component_names = [name for name in self.component_names if name!='noise']
        suffixes = gen_suffixes(base_component_names)
                        
        ## initialize components
        self.components = {}
        self.truevals = {}
        for component_name, suffix in zip(self.component_names,suffixes):
            cm = submodel(params,inj,component_name,fs,f0,tsegmid,injection=True,suffix=suffix)
            self.components[component_name] = cm
            self.truevals.update(cm.truevals)
            if cm.has_map:
                self.plot_skymaps(component_name)
    
        
    
    
    
    def compute_convolved_spectra(self,component_name,fs_new=None,channels='11',return_fs=False,imaginary=False):
        '''
        Wrapper to convolve the frozen response with the frozen injected GW spectra for the desired channels.
        
        Arguments
        -----------
        component_name (str) : the name (key) of the Injection component to use.
        fs_new (array) : If desired, frequencies at which to interpolate the convolved PSD
        channels (str) : Which channel cross/auto-correlation PSD to plot. Default is '11' auto-correlation, i.e. XX for XYZ, 11 for Michelson, AA for AET.
        return_fs (bool) : If True, also returns the frequencies at which the PSD has been evaluated. Default False.
        imaginary (bool) : If True, returns the magnitude of the imaginary component. Default False.
        
        Returns
        -----------
        PSD (array) : Power spectral density of the specified channels' auto/cross-correlation at the desired frequencies.
        fs (array, optional) : The PSD frequencies, if return_fs==True.
        
        '''
        
        cm = self.components[component_name]
        ## split the channel indicators
        c1_idx, c2_idx = int(channels[0]) - 1, int(channels[1]) - 1
        ## populations need some finessing due to frequency subtleties
        if hasattr(cm,"ispop") and cm.ispop:
#            if fs_new is not None and not np.array_equal(fs_new,cm.population.frange_true):
#                print("Warning: population spectra cannot be aribtrarily rebinned. Calculating convolved signal at data frequencies...")
            fs = cm.population.frange_true
            if not imaginary:
                PSD = np.mean(cm.population.Sgw_true[:,None] * np.real(cm.inj_response_mat_true[c1_idx,c2_idx,:,:]),axis=1)
            else:
                PSD = np.mean(cm.population.Sgw_true[:,None] * 1j * np.imag(cm.inj_response_mat_true[c1_idx,c2_idx,:,:]),axis=1)
            if (fs_new is not None) and not np.array_equal(fs_new,cm.population.frange_true):
                PSD_interp = interp1d(fs,PSD)
                PSD = PSD_interp(fs_new)
                fs = fs_new

        else:
            if not imaginary:
                PSD = np.mean(cm.frozen_spectra[:,None] * np.real(cm.inj_response_mat[c1_idx,c2_idx,:,:]),axis=1)
            else:
                PSD = np.mean(cm.frozen_spectra[:,None] * 1j * np.imag(cm.inj_response_mat[c1_idx,c2_idx,:,:]),axis=1)
        
            if fs_new is not None:
                PSD_interp = interp1d(self.frange,np.log10(PSD))
                PSD = 10**PSD_interp(fs_new)
                fs = fs_new
            else:
                fs = self.frange
        
        if return_fs:
            return fs, PSD
        else:
            return PSD

    
    def plot_injected_spectra(self,component_name,fs_new=None,ax=None,convolved=False,legend=False,channels='11',return_PSD=False,scale='log',flim=None,ymins=None,**plt_kwargs):
        '''
        Wrapper to plot the injected spectrum component on the specified matplotlib axes (or current axes if unspecified).
        
        Arguments
        -----------
        component_name (str) : the name (key) of the Injection component to use.
        fs_new (array) : If desired, frequencies at which to interpolate the convolved PSD
        ax (matplotlib axes) : Axis on which to plot. Default None (will plot on current axes.)
        convolved (bool) : If True, convolve the injected spectra with the detector response. Default False.
        legend (bool) : If True, generate a legend entry. Default False.
        channels (str) : Which channel cross/auto-correlation PSD to plot. Default is '11' auto-correlation, i.e. XX for XYZ, 11 for Michelson, AA for AET.
        return_PSD (bool) : If True, also returns the plotted PSD. Default False.
        scale (str) : Matplotlib scale at which to plot ('log' or 'linear'). Default 'log'.
        flim (tuple) : (fmin,fmax) plot limits. Default None (will use fmin,fmax as specified in the params file.)
        ymins (list) : External list to which, if specified, will be added the lower ylim of the injected spectra.
        **plt_kwargs (kwargs) : matplotlib.pyplot keyword arguments
        
        Returns
        -----------
        PSD plot on specified axes.
        PSD (array, optional) : Power spectral density of the specified channels' auto/cross-correlation at the desired frequencies.

        '''
        ## grav component
        cm = self.components[component_name]
        
        ## set axes
        if ax is None:
            ax = plt.gca()
        
        ## set fmin/max to specified values, or default to the ones in params
        if flim is not None:
            fmin = flim[0]
            fmax = flim[1]
        else:
            fmin = self.params['fmin']
            fmax = self.params['fmax']
        
        ## special treatment of population frequencies
#        if hasattr(self.components[component_name],"ispop") and self.components[component_name].ispop:
#            fs_base = self.components[component_name].population.frange_true
#        else:
#        fs_base = self.frange
        
        ## get frozen injected spectra at original injection frequencies and convolve with detector response if desired
        if convolved:
            if component_name == 'noise':
                raise ValueError("Cannot convolve noise spectra with the detector GW response - this is not physical. (Set convolved=False in the function call!)")
            fs, PSD = self.compute_convolved_spectra(component_name,channels=channels,return_fs=True,fs_new=fs_new)
        else:
            ## special treatment for the population case
            if hasattr(cm,"ispop") and cm.ispop:
                PSD = cm.population.Sgw_true
                fs = cm.population.frange_true
                if fs_new is not None and not np.array_equal(fs_new,cm.population.frange_true):
#                    print("Warning: population spectra cannot be aribtrarily rebinned. Plotting at data frequencies...")
##                    PSD = cm.population.rebin_PSD(fs_new)
##                    fs = fs_new
                    PSD_interp = interp1d(fs,PSD)
                    PSD = PSD_interp(fs_new)
                    fs = fs_new
            else:
                PSD = cm.frozen_spectra
                ## noise will return the 3x3 covariance matrix, need to grab the desired channel cross-/auto-power
                ## generically capture anything that looks like a covariance matrix for future-proofing
                if (len(PSD.shape)==3) and (PSD.shape[0]==PSD.shape[1]==3):
                    I, J = int(channels[0]) - 1, int(channels[1]) - 1
                    PSD = PSD[I,J,:]

                ## downsample (or upsample, but why) if desired
                ## do the interpolation in log-space for better low-f fidelity
                if fs_new is not None:
                    PSD_interp = interp1d(self.frange,np.log10(PSD))
                    PSD = 10**PSD_interp(fs_new)
                    fs = fs_new
                else:
                    fs = self.frange
        
        filt = (fs>fmin)*(fs<fmax)
        
        if legend:
            label = cm.fancyname
            if plt_kwargs is None:
                plt_kwargs = {}
                plt_kwargs['label'] = label
            else:
                if 'label' not in plt_kwargs.keys():
                    plt_kwargs['label'] = label
        
        if scale=='log':
            ax.loglog(fs[filt],PSD[filt],**plt_kwargs)
        elif scale=='linear':
            ax.plot(fs[filt],PSD[filt],**plt_kwargs)
        else:
            raise ValueError("We only support linear and log plots, there is no secret third option!")
        
        if ymins is not None:
            ymins.append(PSD.min())
        
        if return_PSD:
            return PSD
        else:
            return
        
    def plot_skymaps(self,component_name,**plt_kwargs):
        '''
        Function to plot the injected skymaps.
        
        NOTE - will need to be generalized when I add the astro injections
        '''
        cm = self.components[component_name]
        
        # deals with projection parameter 
        if self.params['projection'] is None:
            coord = 'E'
        elif self.params['projection']=='G' or self.params['projection']=='C':
            coord = ['E',self.params['projection']]
        elif self.params['projection']=='E':
            coord = self.params['projection']
        else:  
            raise TypeError('Invalid specification of projection, projection can be E, G, or C')
        
        ## dimensionless energy density at 1 mHz
        spec_args = [cm.truevals[parameter] for parameter in cm.spectral_parameters]
        Omega_1mHz = cm.omegaf(1e-3,*spec_args)
        Omegamap_inj = Omega_1mHz * cm.sph_skymap

        hp.mollview(Omegamap_inj, coord=coord, title='Injected angular distribution map $\Omega (f = 1 mHz)$', unit="$\\Omega(f= 1mHz)$")
        hp.graticule()
        
        plt.savefig(self.params['out_dir'] + '/inj_skymap'+component_name+'.png', dpi=150)
        print('saving injected skymap at ' +  self.params['out_dir'] + '/inj_skymap'+component_name+'.png')
        plt.close()
        
        return




def catch_duplicates(names):
    '''
    Function to catch duplicate names so we don't overwrite keys while building a Model or Injection
    
    Arguments
    ---------------
    names (list of str) : model or injection submodel names
    
    Returns
    ---------------
    names (list of str) : model or injection submodel names, with duplicates numbered
    '''
    original_names = names.copy()
    duplicate_check = {name:names.count(name) for name in names}
    for key in duplicate_check.keys():
        if duplicate_check[key] > 1:
            cnt = 1
            for i, original_name in enumerate(original_names):
                if original_name == key:
                    names[i] = original_name + '-' + str(cnt)
    
    return names

def gen_suffixes(names):
    '''
    Function to generate appropriate parameter suffixes so repeated parameters are clearly linked to their respective submodel configurations.
    
    Arguments
    ---------------
    names (list of str) : model or injection submodel names
    
    Returns
    ---------------
    suffixes (list of str) : parameter suffixes for each respective model or injection submodel
    '''
    ## grab the spatial designation (or just 'noise' for the noise case)
    end_lst = [name.split('_')[-1] for name in names]
    ## if we just have noise and a lone signal, we don't need to do this.
    if ('noise' in end_lst) and len(end_lst)==2:
        suffixes = ['','']
        return suffixes
    ## set up our building blocks and model counts for iterative numbering
    shorthand = {'noise':{'abbrv':'','count':1},
                 'isgwb':{'abbrv':'I','count':1},
                 'sph':{'abbrv':'A','count':1},
                 'population':{'abbrv':'P','count':1},
                 'hierarchical':{'abbrv':'H','count':1} }
    
    suffixes = ['  $\mathrm{[' for i in range(len(names))]
    
    ## find duplicates and count them
    dupc = {end:end_lst.count(end) for end in end_lst}
    
    ## generate the suffixes by assigning the abbreviated notation and numbering as necessary
    for i, (end,suff) in enumerate(zip(end_lst,suffixes)):
        if end == 'noise':
            if dupc[end] > 1:
                raise ValueError("Multiple noise injections/models is not supported.")
            else:
                suffixes[i] = ''
        elif dupc[end] == 1:
            suffixes[i] = suff + shorthand[end]['abbrv'] + ']}$'
        else:
            suffixes[i] = suff + shorthand[end]['abbrv'] + '_' + str(shorthand[end]['count']) + ']}$'
            shorthand[end]['count'] += 1

    return suffixes

def gen_blm_parameters(blmax):
    '''
    Function to make the blm parameter name strings for all blms of a given lmax, in the correct order.
    
    Arguments
    -----------
    blmax (int) : lmax for the blms
    
    Returns
    -----------
    blm_parameters (list of str) : Ordered list of blm parameter name strings
    
    '''
    
    blm_parameters = []
    for lval in range(1, blmax + 1):
        for mval in range(lval + 1):

            if mval == 0:
                blm_parameters.append(r'$b_{' + str(lval) + str(mval) + '}$' )
            else:
                blm_parameters.append(r'$|b_{' + str(lval) + str(mval) + '}|$' )
                blm_parameters.append(r'$\phi_{' + str(lval) + str(mval) + '}$' )
    
    return blm_parameters


def bespoke_inv(A):


    """

    compute inverse without division by det; ...xv3xc3 input, or array of matrices assumed

    Credit to Eelco Hoogendoorn at stackexchange for this piece of wizardy. This is > 3 times
    faster than numpy's det and inv methods used in a fully vectorized way as of numpy 1.19.1

    https://stackoverflow.com/questions/21828202/fast-inverse-and-transpose-matrix-in-python

    """


    AI = np.empty_like(A)

    for i in range(3):
        AI[...,i,:] = np.cross(A[...,i-2,:], A[...,i-1,:])

    det = np.einsum('...i,...i->...', AI, A).mean(axis=-1)

    inv_T =  AI / det[...,None,None]

    # inverse by swapping the inverse transpose
    return np.swapaxes(inv_T, -1,-2), det
