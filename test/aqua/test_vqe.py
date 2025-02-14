# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

""" Test VQE """

import unittest
import os
from test.aqua.common import QiskitAquaTestCase

import numpy as np
from parameterized import parameterized
from qiskit import BasicAer

from qiskit.aqua import run_algorithm, QuantumInstance, aqua_globals
from qiskit.aqua.input import EnergyInput
from qiskit.aqua.operators import WeightedPauliOperator
from qiskit.aqua.components.variational_forms import RY
from qiskit.aqua.components.optimizers import L_BFGS_B, COBYLA, SPSA
from qiskit.aqua.components.initial_states import Zero
from qiskit.aqua.algorithms import VQE


class TestVQE(QiskitAquaTestCase):
    """ Test VQE """
    def setUp(self):
        super().setUp()
        # np.random.seed(50)
        self.seed = 50
        aqua_globals.random_seed = self.seed
        pauli_dict = {
            'paulis': [{"coeff": {"imag": 0.0, "real": -1.052373245772859}, "label": "II"},
                       {"coeff": {"imag": 0.0, "real": 0.39793742484318045}, "label": "IZ"},
                       {"coeff": {"imag": 0.0, "real": -0.39793742484318045}, "label": "ZI"},
                       {"coeff": {"imag": 0.0, "real": -0.01128010425623538}, "label": "ZZ"},
                       {"coeff": {"imag": 0.0, "real": 0.18093119978423156}, "label": "XX"}
                       ]
        }
        qubit_op = WeightedPauliOperator.from_dict(pauli_dict)
        self.algo_input = EnergyInput(qubit_op)

    def test_vqe_via_run_algorithm(self):
        """ VQE Via Run Algorithm test """
        coupling_map = [[0, 1]]
        basis_gates = ['u1', 'u2', 'u3', 'cx', 'id']

        params = {
            'problem': {'random_seed': self.seed},
            'algorithm': {'name': 'VQE'},
            'backend': {'name': 'statevector_simulator',
                        'provider': 'qiskit.BasicAer',
                        'coupling_map': coupling_map,
                        'basis_gates': basis_gates},
        }
        result = run_algorithm(params, self.algo_input)
        self.assertAlmostEqual(result['energy'], -1.85727503)
        np.testing.assert_array_almost_equal(result['eigvals'], [-1.85727503], 5)
        ref_opt_params = [-0.58294401, -1.86141794, -1.97209632, -0.54796022,
                          -0.46945572, 2.60114794, -1.15637845, 1.40498879,
                          1.14479635, -0.48416694, -0.66608349, -1.1367579,
                          -2.67097002, 3.10214631, 3.10000313, 0.37235089]
        np.testing.assert_array_almost_equal(result['opt_params'], ref_opt_params, 5)
        self.assertIn('eval_count', result)
        self.assertIn('eval_time', result)

    @parameterized.expand([
        ['SLSQP', 5, 4],
        ['SLSQP', 5, 1],
        ['SPSA', 3, 2],  # max_evals_grouped=n is considered as max_evals_grouped=2 if n>2
        ['SPSA', 3, 1]
    ])
    def test_vqe_optimizers(self, name, places, max_evals_grouped):
        """ VQE Optimizers test """
        backend = BasicAer.get_backend('statevector_simulator')
        params = {
            'algorithm': {'name': 'VQE', 'max_evals_grouped': max_evals_grouped},
            'optimizer': {'name': name},
            'backend': {'shots': 1}
        }
        result = run_algorithm(params, self.algo_input, backend=backend)
        self.assertAlmostEqual(result['energy'], -1.85727503, places=places)

    @parameterized.expand([
        ['RY', 5],
        ['RYRZ', 5]
    ])
    def test_vqe_var_forms(self, name, places):
        """ VQE Var Forms test """
        backend = BasicAer.get_backend('statevector_simulator')
        params = {
            'algorithm': {'name': 'VQE'},
            'variational_form': {'name': name},
            'backend': {'shots': 1}
        }
        result = run_algorithm(params, self.algo_input, backend=backend)
        self.assertAlmostEqual(result['energy'], -1.85727503, places=places)

    def test_vqe_qasm(self):
        """ VQE QASm test """
        backend = BasicAer.get_backend('qasm_simulator')
        num_qubits = self.algo_input.qubit_op.num_qubits
        var_form = RY(num_qubits, 3)
        optimizer = SPSA(max_trials=300, last_avg=5)
        algo = VQE(self.algo_input.qubit_op, var_form, optimizer, max_evals_grouped=1)
        quantum_instance = QuantumInstance(backend, shots=10000,
                                           seed_simulator=self.seed,
                                           seed_transpiler=self.seed)
        result = algo.run(quantum_instance)
        self.assertAlmostEqual(result['energy'], -1.85727503, places=2)

    def test_vqe_statevector_snapshot_mode(self):
        """ VQE Aer statevector_simulator snapshot mode test """
        try:
            # pylint: disable=import-outside-toplevel
            from qiskit import Aer
        except Exception as ex:  # pylint: disable=broad-except
            self.skipTest("Aer doesn't appear to be installed. Error: '{}'".format(str(ex)))
            return
        backend = Aer.get_backend('statevector_simulator')
        num_qubits = self.algo_input.qubit_op.num_qubits
        init_state = Zero(num_qubits)
        var_form = RY(num_qubits, 3, initial_state=init_state)
        optimizer = L_BFGS_B()
        algo = VQE(self.algo_input.qubit_op, var_form, optimizer, max_evals_grouped=1)
        quantum_instance = QuantumInstance(backend)
        result = algo.run(quantum_instance)
        self.assertAlmostEqual(result['energy'], -1.85727503, places=6)

    def test_vqe_qasm_snapshot_mode(self):
        """ VQE Aer qasm_simulator snapshot mode test """
        try:
            # pylint: disable=import-outside-toplevel
            from qiskit import Aer
        except Exception as ex:  # pylint: disable=broad-except
            self.skipTest("Aer doesn't appear to be installed. Error: '{}'".format(str(ex)))
            return
        backend = Aer.get_backend('qasm_simulator')
        num_qubits = self.algo_input.qubit_op.num_qubits
        init_state = Zero(num_qubits)
        var_form = RY(num_qubits, 3, initial_state=init_state)
        optimizer = L_BFGS_B()
        algo = VQE(self.algo_input.qubit_op, var_form, optimizer, max_evals_grouped=1)
        quantum_instance = QuantumInstance(backend, shots=1)
        result = algo.run(quantum_instance)
        self.assertAlmostEqual(result['energy'], -1.85727503, places=6)

    def test_vqe_callback(self):
        """ VQE Callback test """
        tmp_filename = 'vqe_callback_test.csv'
        is_file_exist = os.path.exists(self._get_resource_path(tmp_filename))
        if is_file_exist:
            os.remove(self._get_resource_path(tmp_filename))

        def store_intermediate_result(eval_count, parameters, mean, std):
            with open(self._get_resource_path(tmp_filename), 'a') as file:
                content = "{},{},{:.5f},{:.5f}".format(eval_count, parameters, mean, std)
                print(content, file=file, flush=True)

        backend = BasicAer.get_backend('qasm_simulator')
        num_qubits = self.algo_input.qubit_op.num_qubits
        init_state = Zero(num_qubits)
        var_form = RY(num_qubits, 1, initial_state=init_state)
        optimizer = COBYLA(maxiter=3)
        algo = VQE(self.algo_input.qubit_op, var_form, optimizer,
                   callback=store_intermediate_result, auto_conversion=False)
        aqua_globals.random_seed = 50
        quantum_instance = QuantumInstance(backend,
                                           seed_transpiler=50,
                                           shots=1024,
                                           seed_simulator=50)
        algo.run(quantum_instance)

        is_file_exist = os.path.exists(self._get_resource_path(tmp_filename))
        self.assertTrue(is_file_exist, "Does not store content successfully.")

        # check the content
        ref_content = [['1',
                        '[-0.03391886 -1.70850424 -1.53640265 -0.65137839]',
                        '-0.61121', '0.01572'],
                       ['2',
                        '[ 0.96608114 -1.70850424 -1.53640265 -0.65137839]',
                        '-0.79235', '0.01722'],
                       ['3',
                        '[ 0.96608114 -0.70850424 -1.53640265 -0.65137839]',
                        '-0.82829', '0.01529']
                       ]
        try:
            with open(self._get_resource_path(tmp_filename)) as file:
                idx = 0
                for record in file.readlines():
                    eval_count, parameters, mean, std = record.split(",")
                    self.assertEqual(eval_count.strip(), ref_content[idx][0])
                    self.assertEqual(parameters, ref_content[idx][1])
                    self.assertEqual(mean.strip(), ref_content[idx][2])
                    self.assertEqual(std.strip(), ref_content[idx][3])
                    idx += 1
        finally:
            if is_file_exist:
                os.remove(self._get_resource_path(tmp_filename))


if __name__ == '__main__':
    unittest.main()
