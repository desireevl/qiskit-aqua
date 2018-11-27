# -*- coding: utf-8 -*-

# Copyright 2018 IBM.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================
"""
The Grover Quantum algorithm.
"""

import logging
from qiskit import ClassicalRegister, QuantumCircuit
from qiskit_aqua import QuantumAlgorithm, AquaError
from qiskit_aqua import PluggableType, get_pluggable_class

logger = logging.getLogger(__name__)


class Grover(QuantumAlgorithm):
    """The Grover Quantum algorithm."""

    PROP_INCREMENTAL = 'incremental'
    PROP_NUM_ITERATIONS = 'num_iterations'

    CONFIGURATION = {
        'name': 'Grover',
        'description': 'Grover',
        'input_schema': {
            '$schema': 'http://json-schema.org/schema#',
            'id': 'grover_schema',
            'type': 'object',
            'properties': {
                PROP_INCREMENTAL: {
                    'type': 'boolean',
                    'default': False
                },
                PROP_NUM_ITERATIONS: {
                    'type': 'integer',
                    'default': 1,
                    'minimum': 1
                }
            },
            'additionalProperties': False
        },
        'problems': ['search'],
        'depends': ['oracle'],
        'defaults': {
            'oracle': {
                'name': 'SAT'
            }
        }
    }

    def __init__(self, oracle, incremental=False, num_iterations=1):
        super().__init__()
        self.validate(locals())
        self._oracle = oracle
        self._max_num_iterations = 2 ** (len(self._oracle.variable_register()) / 2)
        self._incremental = incremental
        self._num_iterations = num_iterations
        if incremental:
            logger.debug('Incremental mode specified, ignoring "num_iterations".')
        else:
            if num_iterations > self._max_num_iterations:
                logger.warning('The specified value {} for "num_iterations" might be too high.'.format(num_iterations))
        self._ret = {}

    @classmethod
    def init_params(cls, params, algo_input):
        """
        Initialize via parameters dictionary and algorithm input instance
        Args:
            params: parameters dictionary
            algo_input: input instance
        """
        if algo_input is not None:
            raise AquaError("Unexpected Input instance.")

        grover_params = params.get(QuantumAlgorithm.SECTION_KEY_ALGORITHM)
        incremental = grover_params.get(Grover.PROP_INCREMENTAL)
        num_iterations = grover_params.get(Grover.PROP_NUM_ITERATIONS)

        oracle_params = params.get(QuantumAlgorithm.SECTION_KEY_ORACLE)
        oracle = get_pluggable_class(PluggableType.ORACLE,
                                     oracle_params['name']).init_params(oracle_params)
        return cls(oracle, incremental=incremental, num_iterations=num_iterations)

    def _construct_circuit_components(self):
        measurement_cr = ClassicalRegister(len(self._oracle.variable_register()), name='m')
        if self._oracle.ancillary_register():
            qc_prefix = QuantumCircuit(
                self._oracle.variable_register(),
                self._oracle.ancillary_register(),
                measurement_cr
            )
            qc_amplitude_amplification = QuantumCircuit(
                self._oracle.variable_register(),
                self._oracle.ancillary_register()
            )
        else:
            qc_prefix = QuantumCircuit(
                self._oracle.variable_register(),
                measurement_cr
            )
            qc_amplitude_amplification = QuantumCircuit(
                self._oracle.variable_register()
            )
        qc_prefix.h(self._oracle.variable_register())

        qc_amplitude_amplification += self._oracle.construct_circuit()
        qc_amplitude_amplification.h(self._oracle.variable_register())
        qc_amplitude_amplification.x(self._oracle.variable_register())
        qc_amplitude_amplification.x(self._oracle.outcome_register())
        qc_amplitude_amplification.h(self._oracle.outcome_register())
        if self._oracle.ancillary_register():
            qc_amplitude_amplification.cnx(
                [self._oracle.variable_register()[i] for i in range(len(self._oracle.variable_register()))],
                [self._oracle.ancillary_register()[i] for i in range(len(self._oracle.ancillary_register()))],
                self._oracle.outcome_register()[0]
            )
        else:
            qc_amplitude_amplification.cnx(
                [self._oracle.variable_register()[i] for i in range(len(self._oracle.variable_register()))],
                [],
                self._oracle.outcome_register()[0]
            )
        qc_amplitude_amplification.h(self._oracle.outcome_register())
        qc_amplitude_amplification.x(self._oracle.variable_register())
        qc_amplitude_amplification.x(self._oracle.outcome_register())
        qc_amplitude_amplification.h(self._oracle.variable_register())
        qc_amplitude_amplification.h(self._oracle.outcome_register())

        qc_measurement = QuantumCircuit(
            self._oracle.variable_register(),
            measurement_cr
        )
        qc_measurement.barrier(self._oracle.variable_register())
        qc_measurement.measure(self._oracle.variable_register(), measurement_cr)

        return qc_prefix, qc_amplitude_amplification, qc_measurement

    def _run_with_num_iterations(self, qc_prefix, qc_amplitude_amplification, qc_measurement):
        qc = qc_prefix + qc_amplitude_amplification + qc_measurement
        self._ret['circuit'] = qc
        self._ret['measurements'] = self.execute(qc).get_counts(qc)
        assignment = self._oracle.interpret_measurement(self._ret['measurements'])
        oracle_evaluation = self._oracle.evaluate_classically(assignment)
        return assignment, oracle_evaluation

    def run(self):

        if QuantumAlgorithm.is_statevector_backend(self.backend):
            raise ValueError('Selected backend  "{}" does not support measurements.'.format(
                QuantumAlgorithm.backend_name(self.backend)))

        qc_prefix, qc_amplitude_amplification_single_iteration, qc_measurement = self._construct_circuit_components()
        qc_amplitude_amplification = QuantumCircuit()

        if self._incremental:
            qc_amplitude_amplification += qc_amplitude_amplification_single_iteration
            current_num_iterations = 1
            while current_num_iterations <= self._max_num_iterations:
                assignment, oracle_evaluation = self._run_with_num_iterations(
                    qc_prefix, qc_amplitude_amplification, qc_measurement
                )
                if oracle_evaluation:
                    break
                current_num_iterations += 1
                qc_amplitude_amplification += qc_amplitude_amplification_single_iteration
        else:
            for i in range(self._num_iterations):
                qc_amplitude_amplification += qc_amplitude_amplification_single_iteration
            assignment, oracle_evaluation = self._run_with_num_iterations(
                qc_prefix, qc_amplitude_amplification, qc_measurement
            )

        self._ret['result'] = assignment
        self._ret['oracle_evaluation'] = oracle_evaluation
        return self._ret
