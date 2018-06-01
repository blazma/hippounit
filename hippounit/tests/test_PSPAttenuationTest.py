from quantities.quantity import Quantity
from quantities import mV, nA
import sciunit
from sciunit import Test,Score,ObservationError
import hippounit.capabilities as cap
from sciunit.utils import assert_dimensionless# Converters.
from sciunit.scores import BooleanScore,ZScore # Scores.

try:
    import numpy
except:
    print("NumPy not loaded.")

import matplotlib.pyplot as plt
import matplotlib
#from neuron import h
import collections
import efel
import os
import multiprocessing
import multiprocessing.pool
import functools
import math
from scipy import stats

import json
from hippounit import plottools
import collections


try:
    import cPickle as pickle
except:
    import pickle
import gzip

try:
    import copy_reg
except:
    import copyreg

from types import MethodType

from quantities import mV, nA, ms, V, s

from hippounit import scores

def _pickle_method(method):
    func_name = method.im_func.__name__
    obj = method.im_self
    cls = method.im_class
    return _unpickle_method, (func_name, obj, cls)

def _unpickle_method(func_name, obj, cls):
    for cls in cls.mro():
        try:
            func = cls.__dict__[func_name]
        except KeyError:
            pass
        else:
            break
    return func.__get__(obj, cls)


try:
	copyreg.pickle(MethodType, _pickle_method, _unpickle_method)
except:
	copy_reg.pickle(MethodType, _pickle_method, _unpickle_method)


class PSPAttenuationTest(Test):
    """Tests how much synaptic potential attenuates from the dendrite (different distances) to the soma."""

    def __init__(self, config = {},
                observation = {},

                name="PSP attenuation test" ,
                force_run=False,
                base_directory= None,
                show_plot=True,
                num_of_dend_locations = 15,
                random_seed = 1,
                save_all = True):

        observation = self.format_data(observation)

        Test.__init__(self,observation,name)

        self.required_capabilities += (cap.ProvidesRandomDendriticLocations, cap.ReceivesEPSCstim)

        self.force_run = force_run

        self.show_plot = show_plot
        self.save_all = save_all

        self.base_directory = base_directory
        self.path_temp_data = None #added later, because model name is needed
        self.path_figs = None
        self.path_results = None

        self.logFile = None
        self.test_log_filename = 'test_log.txt'

        self.npool = multiprocessing.cpu_count() - 1

        self.config = config

        self.num_of_dend_locations = num_of_dend_locations
        self.random_seed = random_seed

        description = "Tests the mode and efficacy of back-propagating action potentials on the apical trunk."

    score_type = scores.ZScore_PSPAttenuation

    def format_data(self, observation):

        for key, val in observation.items():
            try:
                observation[key] = float(val)
            except Exception as e:
                quantity_parts = val.split(" ")
                number = float(quantity_parts[0])
                units = " ".join(quantity_parts[1:])
                observation[key] = Quantity(number, units)
        return observation

    def run_stimulus(self, model, locations_weights, tau1, tau2):

        dend, xloc, weight = locations_weights

        traces = {}

        if self.base_directory:
            self.path_temp_data = self.base_directory + 'temp_data/' + 'PSP_attenuation/' + model.name + '/'
        else:
            self.path_temp_data= model.base_directory + 'temp_data/' + 'PSP_attenuation/'


        try:
            if not os.path.exists(self.path_temp_data) and self.save_all:
                os.makedirs(self.path_temp_data)
        except OSError, e:
            if e.errno != 17:
                raise
            pass


        file_name = self.path_temp_data + 'stimulus_at_' + dend+ '(' + str(xloc) + ')_weight_' + str(weight) + '.p'

        if self.force_run or (os.path.isfile(file_name) is False):

            print "input at: " + dend + "(" + str(xloc) + ") with weight: " + str(weight)


            t, v, v_dend = model.run_EPSC_stim_get_vm([dend, xloc], weight, tau1, tau2)

            if self.save_all:
                pickle.dump([t, v, v_dend], gzip.GzipFile(file_name, "wb"))

        else:
            t, v, v_dend = pickle.load(gzip.GzipFile(file_name, "rb"))

        traces[dend, xloc] = [t, v, v_dend] # dictionary, the key is the dendritic location
        return traces

    def calculate_weights(self, traces_no_input, EPSC_amp):

        locations_weights = []

        for key, value in traces_no_input.iteritems():
            s = int(len(value[2])*0.9)
            Vm = numpy.mean(value[2][s:])   #calculate mean at the last 10% of the trace, measured at the dendrite
            weight = - EPSC_amp/Vm
            locations_weights.append([key[0], key[1], weight])

        return locations_weights

    def analyse_traces(self, model, traces_dict_no_input, traces_dict, locations_distances):

        if self.base_directory:
            self.path_figs = self.base_directory + 'figs/' + 'PSP_attenuation/' + model.name + '/'
        else:
            self.path_figs = model.base_directory + 'figs/' + 'PSP_attenuation/'


        try:
            if not os.path.exists(self.path_figs) and self.save_all:
                os.makedirs(self.path_figs)
        except OSError, e:
            if e.errno != 17:
                raise
            pass

        attenuation_values = {}
        '''
        num_of_subplots = len(traces_dict.keys())
        nrows = int(numpy.ceil(numpy.sqrt(num_of_subplots)))
        ncols = int(numpy.ceil(numpy.sqrt(num_of_subplots)))
        i=0
        '''

        for key, value in traces_dict.iteritems():

            dend_depol = traces_dict[key][2] - traces_dict_no_input[key][2]
            soma_depol = traces_dict[key][1] - traces_dict_no_input[key][1]

            max_dend_depol = max(dend_depol)
            max_soma_depol = max(soma_depol)
            attenuation = max_soma_depol / max_dend_depol

            attenuation_values[key] = attenuation
            '''
            plt.figure()
            #plt.subplot(nrows, ncols , i+1)
            plt.plot(traces_dict[key][0], soma_depol, label='SOMA')
            plt.plot(traces_dict[key][0], dend_depol, label=key[0]+'('+str(key[1])+')')
            plt.legend(loc = 0)

            #i+=1
            '''
        #sorted_locations_distances = collections.OrderedDict(sorted(locations_distances.items(), key=lambda x: x[1])) # keys are the dendritic locations, values are they distances from soma

        """ Plotting the traces"""
        distances = self.config['target_distances']
        tolerance = self.config['tolerance']

        for dist in distances:

            d = {key:value for (key,value) in locations_distances.items() if value >= dist - tolerance and value <= dist + tolerance }
            sorted_d = collections.OrderedDict(sorted(d.items(), key=lambda x: x[1])) # keys are the dendritic locations, values are they distances from soma

            columns = 2
            width_ratios=[1]*columns
            frames = len(d.keys())
            if int(numpy.ceil(frames/float(columns))) < 5:
                rows = 5
            else:
                rows = int(numpy.ceil(frames/float(columns)))
            height_ratios=[1]*rows
            #axs=[]

            fig = plt.figure(figsize = (210/25.4, 297/25.4))
            gs = matplotlib.gridspec.GridSpec(rows, columns, height_ratios=height_ratios, width_ratios=width_ratios)
            gs.update(top=0.92, bottom=0.04, left=0.07, right=0.97, hspace=0.75, wspace=0.3)
            #fig, axes = plt.subplots(nrows=int(round(len(traces_results)/2.0)), ncols=2)
            #fig.tight_layout()
            fig.suptitle('Input at ' + str(dist) + '$\pm$' + str(tolerance) + ' um from soma')
            i=0

            for key, value in sorted_d.iteritems():
                label_added = False

                dend_depol = traces_dict[key][2] - traces_dict_no_input[key][2]
                soma_depol = traces_dict[key][1] - traces_dict_no_input[key][1]

                #plt.subplot(gs[i])
                ax = fig.add_subplot(gs[i])
                if not label_added:
                    plt.plot(traces_dict[key][0], soma_depol, label='SOMA')
                    plt.plot(traces_dict[key][0], dend_depol, label='dendrite')
                    label_added = True
                else:
                    plt.plot(traces_dict[key][0], soma_depol)
                    plt.plot(traces_dict[key][0], dend_depol)
                plt.title(key[0]+'('+str("%.2f" % key[1])+') ' + str("%.2f" % locations_distances[key]) + ' um')
                plt.xlabel("ms")
                plt.ylabel("mV")
                i+=1    # next subplot

            #lgd=plt.legend(bbox_to_anchor=(1.0, 1.0), loc = 'upper left')
            handles, labels = ax.get_legend_handles_labels()
            lgd = fig.legend(handles, labels, loc = 'upper right')
            if self.save_all:
                plt.savefig(self.path_figs + 'traces_input_around_' + str(dist)+ '_um' + '.pdf', dpi=600, bbox_inches='tight')

        #print attenuation_values
        return attenuation_values

    def calcs_and_plots(self, model, attenuation_values, locations_distances):

        if self.base_directory:
            self.path_figs = self.base_directory + 'figs/' + 'PSP_attenuation/' + model.name + '/'
        else:
            self.path_figs = model.base_directory + 'figs/' + 'PSP_attenuation/'


        try:
            if not os.path.exists(self.path_figs) and self.save_all:
                os.makedirs(self.path_figs)
        except OSError, e:
            if e.errno != 17:
                raise
            pass

        print "The figures are saved in the directory: ", self.path_figs


        distances = self.config['target_distances']
        tolerance = self.config['tolerance']

        observation = self.observation

        obs_means = []
        obs_stds = []

        PSP_attenuation_features = {}
        PSP_attenuation_mean_features = {}

        for dist in distances:
            obs_means.append(observation['mean_attenuation_soma/dend_'+str(dist)+'_um'])
            obs_stds.append(observation['std_attenuation_soma/dend_'+str(dist)+'_um'])
        plt.figure()
        for key, value in attenuation_values.iteritems():
            PSP_attenuation_features[key] = {'attenuation_soma/dendrite' : value, 'distance' : locations_distances[key]}
            plt.plot(locations_distances[key], value, label = key[0]+'('+str(key[1])+') at '+ str(locations_distances[key]) + ' um', marker='o', linestyle='none' )
        plt.errorbar(distances, obs_means, yerr = obs_stds, label = 'experiment', marker='o', linestyle='none', color='r')
        plt.xlabel('Distance from soma (um)')
        plt.ylabel('Attenuation soma/dendrite')
        plt.title('PSP attenuation')
        lgd = plt.legend(bbox_to_anchor=(1.0, 1.0), loc = 'upper left')
        if self.save_all:
            plt.savefig(self.path_figs + 'PSP_attenuation'+ '.pdf', dpi=800, bbox_extra_artists=(lgd,), bbox_inches='tight')

        """ Calculate and plot the mean of attenuation values"""
        label_added = False
        plt.figure()

        for dist in distances:
            att = numpy.array([])
            for key, value in locations_distances.iteritems():
                if value >= dist - tolerance and value < dist + tolerance:
                    att = numpy.append(att, attenuation_values[key])
            mean_att = numpy.mean(att)
            std_att = numpy.std(att)
            PSP_attenuation_mean_features['mean_attenuation_soma/dend_'+str(dist)+'_um']={'mean': float(mean_att), 'std' : float(std_att)}
            if not label_added:
                plt.errorbar(dist, mean_att, yerr = std_att, marker='o', linestyle='none', color = 'b', label=model.name)
                label_added = True
            else:
                plt.errorbar(dist, mean_att, yerr = std_att, marker='o', linestyle='none', color = 'b')
        plt.errorbar(distances, obs_means, yerr = obs_stds, label = 'experiment', marker='o', linestyle='none', color='r')
        plt.xlabel('Distance from soma (um)')
        plt.ylabel('Mean attenuation soma/dendrite')
        plt.title(' Mean PSP attenuation')
        lgd = plt.legend(bbox_to_anchor=(1.0, 1.0), loc = 'upper left')
        if self.save_all:
            plt.savefig(self.path_figs + 'mean_PSP_attenuation'+ '.pdf', dpi=800, bbox_extra_artists=(lgd,), bbox_inches='tight')

        #print PSP_attenuation_features
        return PSP_attenuation_features, PSP_attenuation_mean_features


    """ observation contains ratio numbers, have no unit"""
    '''
    def validate_observation(self, observation):

        for key, value in observation.iteritems():
            try:
                assert type(observation[key]) is Quantity
            except Exception as e:
                raise ObservationError(("Observation must be of the form "
                                        "{'mean':float*mV,'std':float*mV}"))
    '''

    def generate_prediction(self, model, verbose=False):
        """Implementation of sciunit.Test.generate_prediction."""

        if self.base_directory:
            self.path_results = self.base_directory + 'results/' + 'PSP_attenuation/' + model.name + '/'
        else:
            self.path_results = model.base_directory + 'results/' + 'PSP_attenuation/'

        try:
            if not os.path.exists(self.path_results):
                os.makedirs(self.path_results)
        except OSError, e:
            if e.errno != 17:
                raise
            pass

        filepath = self.path_results + self.test_log_filename
        self.logFile = open(filepath, 'w')


        distances = self.config['target_distances']
        tolerance = self.config['tolerance']
        dist_range = [min(distances) - tolerance, max(distances) + tolerance]
        tau1 = self.config['tau_rise']
        tau2 = self.config['tau_decay']
        EPSC_amp = self.config['EPSC_amplitude']

        locations, locations_distances = model.get_random_locations_multiproc(self.num_of_dend_locations, self.random_seed, dist_range) # number of random locations , seed
        #print dend_locations, actual_distances
        print 'Dendritic locations to be tested (with their actual distances):', locations_distances

        self.logFile.write('Dendritic locations to be tested (with their actual distances):\n'+ str(locations_distances)+'\n')
        self.logFile.write("---------------------------------------------------------------------------------------------------\n")

        weight = 0.0

        locations_weights = []
        for locs in locations:
            locs.append(weight)
            locations_weights.append(locs)
        #print locations_weights

        """ run model without an input"""
        pool = multiprocessing.Pool(self.npool, maxtasksperchild=1)
        run_stimulus_ = functools.partial(self.run_stimulus, model, tau1 = tau1, tau2 = tau2)
        traces_no_input = pool.map(run_stimulus_, locations_weights, chunksize=1)

        pool.terminate()
        pool.join()
        del pool
        traces_dict_no_input = dict(i.items()[0] for i in traces_no_input) # merge list of dicts into single dict

        locations_weights = self.calculate_weights(traces_dict_no_input, EPSC_amp)

        """run model with inputs"""
        pool = multiprocessing.Pool(self.npool, maxtasksperchild=1)
        run_stimulus_ = functools.partial(self.run_stimulus, model, tau1 = tau1, tau2 = tau2)
        traces = pool.map(run_stimulus_, locations_weights, chunksize=1)

        pool.terminate()
        pool.join()
        del pool
        traces_dict = dict(i.items()[0] for i in traces) # merge list of dicts into single dict



        #plt.close('all') #needed to avoid overlapping of saved images when the test is run on multiple models in a for loop
        plt.close('all') #needed to avoid overlapping of saved images when the test is run on multiple models

        attenuation_values = self.analyse_traces(model, traces_dict_no_input, traces_dict, locations_distances)
        PSP_attenuation_model_features, PSP_attenuation_mean_model_features = self.calcs_and_plots(model, attenuation_values, locations_distances)

        prediction = PSP_attenuation_mean_model_features

        '''
        for key, value in traces_dict.items():
            plt.figure()
            plt.plot(value[0], value[1], label='SOMA')
            plt.plot(value[0], value[2], label=key[0]+'('+str(key[1])+')')
            plt.legend(loc = 0)
        '''


        PSP_attenuation_model_features_json = {}
        for key, value in PSP_attenuation_model_features.iteritems():
            PSP_attenuation_model_features_json[str(key)]=value

        file_name_features = self.path_results + 'PSP_attenuation_model_features.json'
        json.dump(PSP_attenuation_model_features_json, open(file_name_features, "wb"), indent=4)

        if self.save_all:
            file_name_features_p = self.path_results + 'PSP_attenuation_model_features.p'
            pickle.dump(PSP_attenuation_model_features, gzip.GzipFile(file_name_features_p, "wb"))

        file_name_mean_features = self.path_results + 'PSP_attenuation_mean_model_features.json'
        json.dump(prediction, open(file_name_mean_features, "wb"), indent=4)

        return prediction

    def compute_score(self, observation, prediction, verbose=False):
        """Implementation of sciunit.Test.score_prediction."""

        distances = self.config['target_distances']

        score_avg, errors= scores.ZScore_PSPAttenuation.compute(observation,prediction, distances)

        file_name=self.path_results+'PSP_attenuation_errors.json'

        json.dump(errors, open(file_name, "wb"), indent=4)

        keys = []
        values = []

        plt.figure()
        for key, value in errors.iteritems():
            keys.append(key)
            values.append(value)
        y=range(len(keys))
        y.reverse()
        plt.plot(values, y, 'o')
        plt.yticks(y, keys)
        plt.title('PSP attenuation errors')
        if self.save_all:
            plt.savefig(self.path_figs + 'PSP_attenuation_errors'+ '.pdf', bbox_inches='tight')

        if self.show_plot:
            plt.show()

        score_json= {'score' : score_avg}
        file_name_score = self.path_results + 'PSP_att_final_score.json'
        json.dump(score_json, open(file_name_score, "wb"), indent=4)

        score=scores.ZScore_PSPAttenuation(score_avg)

        self.logFile.write(str(score)+'\n')
        self.logFile.write("---------------------------------------------------------------------------------------------------\n")
        self.logFile.close()

        return score

    def bind_score(self, score, model, observation, prediction):

        score.related_data["figures"] = [self.path_figs + 'PSP_attenuation.pdf', self.path_figs + 'mean_PSP_attenuation.pdf',
                                        self.path_figs + 'PSP_attenuation_errors.pdf', self.path_results + 'PSP_attenuation_model_features.json',
                                        self.path_results + 'PSP_attenuation_mean_model_features.json', self.path_results + 'PSP_attenuation_errors.json',
                                        self.path_results + 'PSP_att_final_score.json', self.path_results + self.test_log_filename]
        score.related_data["results"] = [self.path_results + 'PSP_attenuation_model_features.json', self.path_results + 'PSP_attenuation_mean_model_features.json', self.path_results + 'PSP_attenuation_errors.json', self.path_results + 'PSP_attenuation_model_features.p', self.path_results + 'PSP_att_final_score.json']
        return score
