import numpy as np
import scipy.signal as sg
from src.instrNoise import instrNoise
from src.geometry import geometry
from scipy.interpolate import interp1d as intrp
import matplotlib.pyplot as plt
import healpy as hp
import os

class LISAdata(geometry, instrNoise):

    '''
    Class for lisa data. Includes methods for generation of gaussian instrumental noise, and generation
    of isotropic stochastic background. Any eventually signal models should be added as methods here. This
    has the Antennapatterns class as a super class.
    '''

    def __init__(self, params, inj):
        self.params = params
        self.inj = inj
        self.armlength = 2.5e9 ## armlength in meters
        geometry.__init__(self)


    ## Method for reading frequency domain spectral data if given in an npz file
    def read_spectrum(self):

        '''
        Read an input frequency domain data file. Returns the fourier transform of the data from the three channels and an array of reference frequencyes

        Returns
        ---------

        rA, rE, rT, fdata   :   float

        '''

        if os.path.isfile(self.params['input_spectrum']) and not self.params['doPreProc']:
            print("loading freq domain data from input file")

            data = np.load(self.params['out_dir'] + '/' +self.params['input_spectrum'])
            r1    = data['r1']
            r2    = data['r2']
            r3    = data['r3']
            fdata = data['fdata']

            return r1, r2, r3, fdata


    def gaussianData(self, Sh,freqs, fs=1, dur=1e5):

        '''
        Script for generation time series noise drawn from a gaussian process of a given spectral density.  Adapted from gaussian_noise.m from stamp

        Parameters
        -----------

        Sh : (float)
            A frequency array with the desired power spectral density
        freqs : (float)
            An array with corresponding frequencies to Sh

        fs : (float)
            SampleRate in Hz

        dur : (int)
            Duration in seconds


        Returns
        ---------

        ht : float
        Array with time series data of duration, dur with the prescribed spectrum Sh


        '''

        # Number of data points in the time series
        N = int(fs*dur)

        # prepare for FFT
        if  np.mod(N,2)== 0 :
            numFreqs = int(N/2 - 1)
        else:
            numFreqs = int((N-1)/2)

        # We will make an array of the desired frequencies
        delF = 1/dur
        fmin = 0
        fmax = np.around(dur*fs/2)/dur
        delF = 1/dur

        # The output frequency series
        fout = np.linspace(fmin, fmax, numFreqs)

        # Interpolate to the desired frequencies
        norms = np.interp(fout, freqs, Sh)

        # Amplitude for for ifft
        norms = np.sqrt(norms*fs*N)/2.0

        # Normally distributed in frequency space
        re1 = norms*np.random.normal(size=fout.size)
        im1 = norms*np.random.normal(size=fout.size)

        htilda = re1 + 1j*im1

        if np.mod(N, 2) == 0:
            htilda = np.concatenate((np.zeros(1), htilda,np.zeros(1), np.flipud(np.conjugate(htilda))))
        else:
            htilda = np.concatenate((np.zeros(1),htilda, np.conjugate(np.flipud(htilda))))

        # Take inverse fft to get time series data
        ht = np.real(np.fft.ifft(htilda, N))

        return ht

    def freqdomain_gaussianData(self, Sh,freqs, fs=1, dur=1e5):

        '''
        Script to generate freq Domain gaussian data of a given spectral density.

        Parameters
        -----------

        Sh : (float)
            A frequency array with the desired power spectral density
        freqs : (float)
            An array with corresponding frequencies to Sh

        fs : (float)
            SampleRate in Hz

        dur : (int)
            Duration in seconds


        Returns
        ---------

        ht : float
        frequency domain gaussian.
        '''

        # Number of data points in the time series
        N = int(fs*dur)

        # prepare for FFT
        if  np.mod(N,2)== 0 :
            numFreqs = N/2 - 1;
        else:
            numFreqs = (N-1)/2;

        # We will make an array of the desired frequencies
        delF = 1/dur
        fmin = 1/dur
        fmax = np.around(dur*fs/2)/dur
        delF = 1/dur

        # The output frequency series
        fout = np.linspace(fmin, fmax, numFreqs)

        # Interpolate to the desired frequencies
        norms = np.interp(fout, freqs, Sh)

        # Amplitude for for ifft
        norms = np.sqrt(norms*fs*N)/2.0

        # Normally distributed in frequency space
        re1 = norms*np.random.normal(size=fout.size)
        im1 = norms*np.random.normal(size=fout.size)

        htilda = re1 + 1j*im1


        return htilda, fout


    def gen_michelson_noise(self):

        '''
        Generate interferometric michelson (time-domain) noise, using freqDomain.fundamental_noise_spectrum

        Returns
        ---------
        h1, h2, h3 : float
            Time series data for the three michelson channels
        '''

        # --------------------- Generate Fake Noise -----------------------------
        print("Simulating instrumental noise ...")

       # speed of light
        cspeed = 3e8 #m/s
        delf  = 1.0/self.params['dur']
        frange = np.arange(self.params['fmin'], self.params['fmax'], delf) # in Hz
        fstar = 3e8/(2*np.pi*self.armlength)
        f0 = frange/(2*fstar)

        Sp, Sa = self.fundamental_noise_spectrum(frange, Np=10**self.inj['log_Np'], Na=10**self.inj['log_Na'])

        # Generate data
        np12 = self.gaussianData(Sp, frange, self.params['fs'], 1.1*self.params['dur'])
        np21 = self.gaussianData(Sp, frange, self.params['fs'], 1.1*self.params['dur'])
        np13 = self.gaussianData(Sp, frange, self.params['fs'], 1.1*self.params['dur'])
        np31 = self.gaussianData(Sp, frange, self.params['fs'], 1.1*self.params['dur'])
        np23 = self.gaussianData(Sp, frange, self.params['fs'], 1.1*self.params['dur'])
        np32 = self.gaussianData(Sp, frange, self.params['fs'], 1.1*self.params['dur'])

        na12 = self.gaussianData(Sa, frange, self.params['fs'], 1.1*self.params['dur'])
        na21 = self.gaussianData(Sa, frange, self.params['fs'], 1.1*self.params['dur'])
        na13 = self.gaussianData(Sa, frange, self.params['fs'], 1.1*self.params['dur'])
        na31 = self.gaussianData(Sa, frange, self.params['fs'], 1.1*self.params['dur'])
        na23 = self.gaussianData(Sa, frange, self.params['fs'], 1.1*self.params['dur'])
        na32 = self.gaussianData(Sa, frange, self.params['fs'], 1.1*self.params['dur'])

        # time array and time shift array
        tarr =  np.arange(0, 1.1*self.params['dur'], 1.0/self.params['fs'])
        tarr = tarr[0:np12.size]
        delt = tarr[2] - tarr[1]

        # We start with assuming a padding of 20 seconds on the beginning for the
        # Michelson channels
        ## Using up ten seconds here.
        ten_idx = int(self.params['fs']*10)

        # To implement TDI we need time shifts of multiples of L.
        tlag  = self.armlength/cspeed

        ## One way dopper channels for each arms. Using up seconds of the pad here for doing tlag
        f21 = intrp(tarr, na21, kind='cubic', fill_value='extrapolate')
        f12 = intrp(tarr, na12, kind='cubic', fill_value='extrapolate')
        f32 = intrp(tarr, na32, kind='cubic', fill_value='extrapolate')
        f23 = intrp(tarr, na23, kind='cubic', fill_value='extrapolate')
        f13 = intrp(tarr, na13, kind='cubic', fill_value='extrapolate')
        f31 = intrp(tarr, na31, kind='cubic', fill_value='extrapolate')

        h12  = np12[ten_idx:] - na12[ten_idx:] + f21(tarr[ten_idx:]-tlag)
        h21  = np21[ten_idx:] + na21[ten_idx:] - f12(tarr[ten_idx:]-tlag)

        h23  = np23[ten_idx:] - na23[ten_idx:] + f32(tarr[ten_idx:]-tlag)
        h32  = np32[ten_idx:] + na32[ten_idx:] - f23(tarr[ten_idx:]-tlag)

        h31  = np31[ten_idx:] - na31[ten_idx:] + f13(tarr[ten_idx:]-tlag)
        h13  = np13[ten_idx:] + na13[ten_idx:] - f31(tarr[ten_idx:]-tlag)

        ## reduce tarr
        tarr = tarr[ten_idx:]

        # The Michelson channels, formed from the doppler channels. Using the other
        # ten seconds here

        f12 = intrp(tarr, h12, kind='cubic', fill_value='extrapolate')
        f13 = intrp(tarr, h13, kind='cubic', fill_value='extrapolate')
        f23 = intrp(tarr, h23, kind='cubic', fill_value='extrapolate')
        f21 = intrp(tarr, h21, kind='cubic', fill_value='extrapolate')
        f31 = intrp(tarr, h31, kind='cubic', fill_value='extrapolate')
        f32 = intrp(tarr, h32, kind='cubic', fill_value='extrapolate')


        h1 = f12(tarr[ten_idx:]-tlag) + h21[ten_idx:] - \
                f13(tarr[ten_idx:]-tlag)  - h31[ten_idx:]

        h2 = f23(tarr[ten_idx:]-tlag) + h32[ten_idx:] - \
                f21(tarr[ten_idx:]-tlag)  - h12[ten_idx:]

        h3 = f31(tarr[ten_idx:]-tlag)  + h13[ten_idx:] - \
                f32(tarr[ten_idx:]-tlag)  - h23[ten_idx:]


        '''
        Older way of doing time shifts is commented out here. Interp doesn't work since it
        creates correlated samples, but I leave it here for reference. - Sharan

        h1 = np.interp(tshift, tarr, h12, left=h12[0]) + h21 -\
        np.interp(tshift, tarr, h13, left=h13[0]) - h31

        h2 = np.interp(tshift, tarr, h23, left=h23[0]) + h32 -\
        np.interp(tshift, tarr, h21, left=h21[0]) - h12

        h3 = np.interp(tshift, tarr, h31, left=h31[0]) + h13 -\
        np.interp(tshift, tarr, h32, left=h32[0]) - h23
        '''

        return tarr[ten_idx:], h1, h2, h3



    def gen_xyz_noise(self):

        '''
        Generate interferometric A, E and T channel TDI (time-domain) noise, using freqDomain.fundamental_noise_spectrum

        Returns
        ---------

        h1_noi, h2_noi, h3_noi : float
            Time series data for the three TDI channels

        '''

        '''

        '''
        cspeed = 3e8 #m/s

        # michelson channels
        tarr, hm1, hm2, hm3 = self.gen_michelson_noise()

        ## Using up ten seconds here.
        ten_idx = int(self.params['fs']*10)

        # Introduce time series
        tshift = 2*self.armlength/cspeed

        f1 = intrp(tarr, hm1, kind='cubic', fill_value='extrapolate')
        f2 = intrp(tarr, hm2, kind='cubic', fill_value='extrapolate')
        f3 = intrp(tarr, hm3, kind='cubic', fill_value='extrapolate')


        hX = hm1[ten_idx:] - f1(tarr[ten_idx:] - tshift)
        hY = hm2[ten_idx:] - f2(tarr[ten_idx:] - tshift)
        hZ = hm3[ten_idx:] - f3(tarr[ten_idx:] - tshift)

        return tarr[ten_idx:], hX, hY, hZ



    def gen_aet_noise(self):

        '''
        Generate interferometric A, E and T channel TDI (time-domain) noise, using freqDomain.fundamental_noise_spectrum

        Returns
        ---------
        h1_noi, h2_noi, h3_noi : float
            Time series data for the three TDI channels

        '''

        cspeed = 3e8 #m/s

        # michelson channels
        tarr, hX, hY, hZ = self.gen_xyz_noise()

        h1_noi = (1.0/3.0)*(2*hX - hY - hZ)
        h2_noi = (1.0/np.sqrt(3.0))*(hZ - hY)
        h3_noi = (1.0/3.0)*(hX + hY + hZ)

        return tarr, h1_noi, h2_noi, h3_noi


    def gen_noise_cov_mat(self):

        '''
        Generate interferometric (time-domain) noise, using a frequency domain covariance
        spectrum matrix rather than time delays in time domain.
        ---------

        h1_noi, h2_noi, h3_noi : float
            Time series data for the three TDI channels
        '''

        cspeed = 3e8 #m/s
        delf  = 1.0/self.params['dur']
        fstar = 3e8/(2*np.pi*self.armlength)
        f0 = frange/(2*fstar)

        N = int(self.params['fs']*self.params['dur'])

        frange = np.fft.rfftfreq(N, 1.0/self.params['fs'])[1:]


        #Sp, Sa = self.fundamental_noise_spectrum(frange, Np=10**self.inj['log_Np'], Na=10**self.inj['log_Na'])

        C_xyz = self.xyz_noise_spectrum(frange, f0, Np=10**self.inj['log_Np'], Na=10**self.inj['log_Na'])

        ## Cholesky decomposition to get the "sigma" matrix
        L_cholesky = np.sqrt(self.params['fs'] * N/4.0) *  np.linalg.cholesky(np.moveaxis(C_xyz, -1, 0))

        ## generate standard normal complex data frist
        z_norm = np.random.normal(size=(3, frange.size)) + 1j * np.random.normal(size=(3, frange.size))

        ## initialize a new scaled array. The data in z_norm will be rescaled into z_scale
        z_scale = np.zeros(z_norm.shape, dtype='complex')

        for ii in range(frange.size):
            z_scale[:, ii] = np.matmul(L_cholesky[ii, :, :], z_norm[:, ii])


        ## The three channels
        htilda1  = np.concatenate([ [0], z_scale[0, :]])
        htilda2  = np.concatenate([ [0], z_scale[1, :]])
        htilda3  = np.concatenate([ [0], z_scale[2, :]])


        # Take inverse fft to get time series data
        h1 = np.real(np.fft.ifft(htilda1, N))
        h2 = np.real(np.fft.ifft(htilda2, N))
        h3 = np.real(np.fft.ifft(htilda3, N))

        tarr =  np.arange(0, self.params['dur'], 1.0/self.params['fs'])


        return tarr, h1, h2, h3

    def add_sgwb_data(self, fs=0.25, dur=1e5):

        
        cspeed = 3e8 #m/s
        delf  = 1.0/self.params['dur']
        N = int(self.params['fs']*self.params['dur'])

        frange = np.fft.rfftfreq(N, 1.0/self.params['fs'])
        #frange = np.arange(self.params['fmin'], self.params['fmax'], delf) # in Hz

        fstar = 3e8/(2*np.pi*self.armlength)
        f0 = frange/(2*fstar)

        response_mat = self.add_astro_signal(f0)

        ## Cholesky decomposition to get the "sigma" matrix
        H0 = 2.2*10**(-18) ## in SI units
        Omegaf = (10**self.inj['ln_omega0'])*(frange/(self.params['fref']))**self.inj['alpha']

        # Spectrum of the SGWB
        Sgw = Omegaf*(3/(4*frange**3))*(H0/np.pi)**2

        ## set Sgw[f=0] = 0 to avoid nans
        Sgw[0] = 0

        norms = np.sqrt(self.params['fs']*Sgw*N)

        if self.inj['injtype'] == 'isgwb':
            L_cholesky = norms[:, None, None] *  np.linalg.cholesky(np.moveaxis(response_mat, -1, 0))

        elif self.inj['injtype'] == 'sph_sgwb':

            ## get alms
            alms_inj = self.blm_2_alm(self.inj['blms'])

            ## converts alm_inj into a healpix max to be plotted and saved
            skymap_inj = hp.alm2map(alms_inj, self.params['nside'])

            hp.mollview(skymap_inj, title='Angular distribution map')
            plt.savefig(self.params['out_dir'] + '/inj_skymap.png', dpi=150)
            print('saving injected skymap at ' +  self.params['out_dir'] + '/inj_skymap.png')
            plt.close()

            ## response matrix summed over Ylms
            summ_response_mat = np.sum(response_mat*alms_inj[None, None, None, :], axis=-1)
            L_cholesky = norms[:, None, None] *  np.linalg.cholesky(np.moveaxis(summ_response_mat, -1, 0))


        ## generate standard normal complex data frist
        z_norm = np.random.normal(size=(3, frange.size)) + 1j * np.random.normal(size=(3, frange.size))

        ## initialize a new scaled array. The data in z_norm will be rescaled into z_scale
        z_scale = np.zeros(z_norm.shape, dtype='complex')

        for ii in range(frange.size):
            z_scale[:, ii] = np.matmul(L_cholesky[ii, :, :], z_norm[:, ii])


        ## The three channels
        htilda1, htilda2, htilda3 = z_scale[0, :],  z_scale[1, :], z_scale[2, :],

        # Take inverse fft to get time series data
        h1 = np.real(np.fft.ifft(htilda1, N))
        h2 = np.real(np.fft.ifft(htilda2, N))
        h3 = np.real(np.fft.ifft(htilda3, N))

        tarr =  np.arange(0, self.params['dur'], 1.0/self.params['fs'])

        return h1, h2, h3, tarr

    def add_earlygw_data(self, fs=0.25, dur=1e5):

        cspeed = 3e8 #m/s
        delf  = 1.0/self.params['dur']
        frange = np.arange(self.params['fmin'], self.params['fmax'], delf) # in Hz
        fstar = 3e8/(2*np.pi*self.armlength)
        f0 = frange/(2*fstar)

        N = int(self.params['fs']*self.params['dur'])

        response_mat = self.add_astro_signal(f0)

        ## Cholesky decomposition to get the "sigma" matrix
        H0 = 2.2*10**(-18) ## in SI units
        # Calculate noise in case 1, no r and omega0
        g_bbn = 10.75
        gs_bbn = 10.75
        g_eq = 3.3626
        gs_eq = 3.9091
        del_R = 2.25*10**-9
        z_bbn = 5.9*10**9 - 1
        kcmb = 0.05

        gamma = ((2.3*10**4))**-1 * (g_bbn/g_eq) * (gs_eq/gs_bbn)**1.3333

        A1 = (del_R**2)*gamma/24
        A2 = (2*np.pi*frange/H0) * (1 / (gamma**0.5 * (1 + z_bbn)))
        A3 = (2*np.pi*frange/H0) * (0.72/150.)

        alpha_hat = 2 * (3 * self.inj['wHat'] - 1) / (3 * self.inj['wHat'] + 1)
        Omegaf = self.inj['rts']*(A1 * A2**alpha_hat * A3**self.inj['nHat'])

        # Spectrum of the SGWB
        Sgw = Omegaf*(3/(4*frange**3))*(H0/np.pi)**2
        norms = np.sqrt(self.params['fs']*Sgw*N)

        L_cholesky = norms[:, None, None] *  np.linalg.cholesky(np.moveaxis(response_mat, -1, 0))
        
        ## generate standard normal complex data frist
        z_norm = np.random.normal(size=(3, frange.size)) + 1j * np.random.normal(size=(3, frange.size))

        ## initialize a new scaled array. The data in z_norm will be rescaled into z_scale
        z_scale = np.zeros(z_norm.shape, dtype='complex')

        for ii in range(frange.size):
            z_scale[:, ii] = np.matmul(L_cholesky[ii, :, :], z_norm[:, ii])


        if np.mod(N, 2) == 0:
            htilda_X = np.concatenate((np.zeros(1), z_scale[0, :], np.zeros(1), np.flipud(np.conjugate(z_scale[0, :]))))
            htilda_Y = np.concatenate((np.zeros(1), z_scale[1, :], np.zeros(1), np.flipud(np.conjugate(z_scale[1, :]))))
            htilda_Z = np.concatenate((np.zeros(1), z_scale[2, :], np.zeros(1), np.flipud(np.conjugate(z_scale[2, :]))))
        else:
            htilda_X = np.concatenate((np.zeros(1), z_scale[0, :], np.flipud(np.conjugate(z_scale[0, :]))))
            htilda_Y = np.concatenate((np.zeros(1), z_scale[1, :], np.flipud(np.conjugate(z_scale[1, :]))))
            htilda_Z = np.concatenate((np.zeros(1), z_scale[2, :], np.flipud(np.conjugate(z_scale[2, :]))))

        # Take inverse fft to get time series data
        hX = np.real(np.fft.ifft(htilda_X, N))
        hY = np.real(np.fft.ifft(htilda_Y, N))
        hZ = np.real(np.fft.ifft(htilda_Z, N))

        tarr =  np.arange(0, self.params['dur'], 1.0/self.params['fs'])

        return hX, hY, hZ, tarr


    def add_sgwb_data_tshift(self, fs=0.25, dur=1e5):

        '''
        Wrapper function for generating stochastic data. The output are time domain data
        in whatever TDI levels are chosen,  at the three vertices oft the constellation.

        Returns
        ---------

        h1_gw, h2_gw, h3_gw : float
            Time series stochastic data

        '''

        # --------------------- Generate Fake Data + Noise -----------------------------
        print(" Adding sgwb signal ...")



        dur  = 1.1*self.params['dur']
        seglen =  self.params['seglen']

        # speed of light
        cspeed = 3e8 #m/s

        delf  = 1.0/seglen
        N, Nmid = int(self.params['fs']*seglen), int(0.5*self.params['fs']*seglen)

        tmids = np.arange(0.5*seglen, dur, 0.5*seglen )

        ## Get freqs
        freqs = np.fft.rfftfreq(int(seglen*self.params['fs']), 1.0/self.params['fs'] )

        freqs[0] = 1e-15
        #Charactersitic frequency
        fstar = cspeed/(2*np.pi*self.armlength)

        # define f0 = f/2f*
        f0 = freqs/(2*fstar)


        fidx = np.logical_and(freqs >= self.params['fmin'], freqs <= self.params['fmax'])

        H0 = 2.2*10**(-18) ## in SI units
        Omegaf = (10**self.inj['ln_omega0'])*(freqs/(self.params['fref']))**self.inj['alpha']


        # Spectrum of the SGWB
        Sgw = Omegaf*(3/(4*freqs**3))*(H0/np.pi)**2
        norms = np.sqrt(self.params['fs']*Sgw*N)/2
        norms[0] = 0
        h1, h2, h3 = np.array([]), np.array([]), np.array([])

        sin_N, cos_N = np.sin(np.pi*np.arange(0, Nmid)/N), np.sin(np.pi*np.arange(Nmid, N)/N)

        for ii in range(tmids.size):

            R1, R2, R3 = self.add_astro_signal(f0)

            htilda1 = norms*(R1[:,0] + R1[:,1])
            htilda2 = norms*(R2[:,0] + R2[:,1])
            htilda3 = norms*(R3[:,0] + R3[:,1])


            # Take inverse fft to get time series data
            ht1 = np.real(np.fft.irfft(htilda1, N))
            ht2 = np.real(np.fft.irfft(htilda2, N))
            ht3 = np.real(np.fft.irfft(htilda3, N))

            if ii == 0:
                h1, h2, h3 = np.append(h1, ht1), np.append(h2, ht2), np.append(h3, ht1)
            else:

                h1[-Nmid:] = h1[-Nmid:]*cos_N + ht1[0:Nmid]*sin_N
                h2[-Nmid:] = h2[-Nmid:]*cos_N + ht2[0:Nmid]*sin_N
                h3[-Nmid:] = h3[-Nmid:]*cos_N + ht3[0:Nmid]*sin_N

                h1, h2, h3 = np.append(h1, ht1[Nmid:]), np.append(h2, ht2[Nmid:]), np.append(h3, ht1[Nmid:])

        times = (1.0/self.params['fs'])*np.arange(0, h1.size)

        return h1, h2, h3, times


    def read_data(self):

        '''
        Read mldc domain data from an ascii txt file. Since this was used primarily for
        the MLDC, it assumes that the data is given in X,Y and Z channels.
        Returns
        ---------

        h1, h2, h3 : float
            Time series data for the three TDI channels


        '''

        hoft = np.loadtxt(self.params['datafile'])

        fs_default = 1.0/(hoft[1, 0] - hoft[0, 0])

        ## Read in the duration seconds of data + one segment of buffer
        end_idx = int((self.params['dur'] + self.params['seglen'])*fs_default)

        ## the mldc data is X,Y,Z tdi
        times, h1, h2, h3 = hoft[0:end_idx, 0], hoft[0:end_idx, 1], hoft[0:end_idx, 2], hoft[0:end_idx, 3]

        delt = times[1] - times[0]


        ## Check if the requested sampel rate is consistant
        if self.params['fs'] != 1.0/delt:
            self.params['fs'] = 1.0/delt

        return h1, h2, h3, times



    def tser2fser(self, h1, h2, h3, timearray):

        '''
        Convert time domain data to fourier domain and return ffts. The convention is that the
        the ffts are divided by the sampling frequency and corrected for windowing. A hann window
        is applied by default when moving to the fourier domain. The ffts are also normalized so that
        thier square gives the PSD.

        Parameters
        -----------
        h1, h2, h3 : float
            time series data for the three input channels

        timearray : float
            times corresponding to data in h1, h2, h3

        Returns
        ---------

        r1, r2, r3 : float
            frequency series data for the three input channels

        fdata : float
            Reference frequency series

        tsegstart : float
            Segmented time array giving segment start points

        tsegmid : float
            Segmented time array giving segment midpoints


        '''

        print ("Calculating fourier spectra... ")

        #data = np.concatenate((timearray[:, None], h1[:, None], h2[:, None], h3[:, None]),axis=1 )
        #np.savetxt('owndata_2e7_xyz.txt', data)

        # Number of segmants
        nsegs = int(np.floor(self.params['dur']/self.params['seglen'])) -1

        Nperseg=int(self.params['fs']*self.params['seglen'])

        # Apply band pass filter
        '''
        order = 16
        zz, pp, kk = sg.butter(order, [0.5*self.params['fmin']/(self.params['fs']/2), 0.4*self.params['fs']/(self.params['fs']/2)], btype='bandpass', output='zpk')
        sos = sg.zpk2sos(zz, pp, kk)

        h1 = sg.sosfiltfilt(sos, h1)
        h2 = sg.sosfiltfilt(sos, h2)
        h3 = sg.sosfiltfilt(sos, h3)
        '''

        fftfreqs = np.fft.rfftfreq(Nperseg, 1.0/self.params['fs'])


        # Map of spectrum
        r1 = np.zeros((fftfreqs.size, nsegs), dtype='complex')
        r2 = np.zeros((fftfreqs.size, nsegs), dtype='complex')
        r3 = np.zeros((fftfreqs.size, nsegs), dtype='complex')


        # Hann Window
        hwin = np.hanning(Nperseg)
        win_fact = np.mean(hwin**2)


        zpad = np.zeros(Nperseg)

        ## Initiate time segment arrays
        tsegstart = np.zeros(nsegs)
        tsegmid = np.zeros(nsegs)

        # We will use 50% overlapping segments
        for ii in range(0, nsegs):

            idxmin = int(ii*Nperseg)
            idxmax = idxmin + Nperseg
            idxmid = idxmin + int(Nperseg/2)
            if hwin.size != h1[idxmin:idxmax].size:
                import pdb; pdb.set_trace()

            r1[:, ii] =   np.fft.rfft(hwin*h1[idxmin:idxmax], axis=0)
            r2[:, ii] =   np.fft.rfft(hwin*h2[idxmin:idxmax], axis=0)
            r3[:, ii] =   np.fft.rfft(hwin*h3[idxmin:idxmax], axis=0)


            ## There's probably a more pythonic way of doing this, but it'll work for now.
            tsegstart[ii] = timearray[idxmin]
            tsegmid[ii] = timearray[idxmid]

        # "Cut" to desired frequencies
        idx = np.logical_and(fftfreqs >=  self.params['fmin'] , fftfreqs <=  self.params['fmax'])

        # Output arrays
        fdata = fftfreqs[idx]


        # Get desired frequencies only
        # We want to normalize ffts so thier square give the psd
        # win_fact is to adjust for hann windowing, sqrt(2) for single sided
        r1 = np.sqrt(2/win_fact)*r1[idx, :]/(self.params['fs']*np.sqrt(self.params['seglen']))
        r2 = np.sqrt(2/win_fact)*r2[idx, :]/(self.params['fs']*np.sqrt(self.params['seglen']))
        r3 = np.sqrt(2/win_fact)*r3[idx, :]/(self.params['fs']*np.sqrt(self.params['seglen']))


        np.savez(self.params['out_dir'] + '/' +self.params['input_spectrum'], r1=r1, r2=r2, r3=r3, fdata=fdata)

        return r1, r2, r3, fdata, tsegstart, tsegmid


