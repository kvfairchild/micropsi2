
from micropsi_core.nodenet.stepoperators import StepOperator, Propagate, Calculate
import theano
from theano import tensor as T
from theano import shared
from theano import function
from theano.tensor import nnet as N
import theano.sparse as ST
import numpy as np
from micropsi_core.nodenet.theano_engine.theano_node import *
from micropsi_core.nodenet.theano_engine.theano_definitions import *


class TheanoPropagate(Propagate):
    """
        theano implementation of the Propagate operator.

        Propagates activation from a across w back to a (a is the gate vector and becomes the slot vector)

        every entry in the target vector is the sum of the products of the corresponding input vector
        and the weight values, i.e. the dot product of weight matrix and activation vector

    """

    def execute(self, nodenet, nodes, netapi):
        for section in nodenet.sections.values():
            section.propagate()

class TheanoCalculate(Calculate):
    """
        theano implementation of the Calculate operator.

        implements node and gate functions as a theano graph.

    """

    def __init__(self, nodenet):
        self.calculate = None
        self.world = None
        self.nodenet = nodenet

    def read_sensors_and_actuator_feedback(self):
        if self.world is None:
            return

        datasource_to_value_map = {}
        for datasource in self.world.get_available_datasources(self.nodenet.uid):
            datasource_to_value_map[datasource] = self.world.get_datasource(self.nodenet.uid, datasource)

        datatarget_to_value_map = {}
        for datatarget in self.world.get_available_datatargets(self.nodenet.uid):
            datatarget_to_value_map[datatarget] = self.world.get_datatarget_feedback(self.nodenet.uid, datatarget)

        self.nodenet.set_sensors_and_actuator_feedback_to_values(datasource_to_value_map, datatarget_to_value_map)

    def write_actuators(self):
        if self.world is None:
            return

        values_to_write = self.nodenet.read_actuators()
        for datatarget in values_to_write:
            self.world.add_to_datatarget(self.nodenet.uid, datatarget, values_to_write[datatarget])

    def count_success_and_failure(self, nodenet):
        nays = 0
        yays = 0
        for section in nodenet.sections.values():
            if section.has_pipes:
                nays += len(np.where((section.n_function_selector.get_value(borrow=True) == NFPG_PIPE_SUR) & (section.a.get_value(borrow=True) <= -1))[0])
                yays += len(np.where((section.n_function_selector.get_value(borrow=True) == NFPG_PIPE_SUR) & (section.a.get_value(borrow=True) >= 1))[0])
        nodenet.set_modulator('base_number_of_expected_events', yays)
        nodenet.set_modulator('base_number_of_unexpected_events', nays)

    def execute(self, nodenet, nodes, netapi):
        self.world = nodenet.world

        self.write_actuators()
        self.read_sensors_and_actuator_feedback()
        for section in nodenet.sections.values():
            section.calculate()
        self.count_success_and_failure(nodenet)


class TheanoPORRETDecay(StepOperator):
    """
    Implementation of POR/RET link decaying.
    This is a pure numpy implementation right now, as theano doesn't like setting subtensors with fancy indexing
    on sparse matrices.
    """

    @property
    def priority(self):
        return 100

    def execute(self, nodenet, nodes, netapi):
       for section in nodenet.sections.values():
            section.por_ret_decay()