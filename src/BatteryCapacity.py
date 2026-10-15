import numpy as np

from Models import BatteryPack, Tire, Transmission, Motor, Vehicle, Pedal
from Simulation.Simulation import Simulation 
from Brake import BrakeSystem
from config.battery_config import BATTERY_PARAMS
from visualization.energy_plots import plot_sprint_energy



tire_params = {
            'pacejka_params': dict(Tire.Tire.HOOSIER_FSAE_LONG),
            'tire_friction_coef': 0.6,
            'Fz0': 654.0,
            'camber': 0.0,
        }

transmission_params = {
        'final_drive_ratio': 5.0,
        'Z_pinhao': None,
        'Z_coroa':  None,
        'chain_efficiency': 0.98,
        'diff_efficiency': 0.97,
        'axle_inertia': 0.0015,
        'diff_inertia': 0.012,
        'sprocket_inertia': 0.0002,
        'coroa_inertia':  0.0015,
        'lsd_bias_ratio': 3.0,
    }

motor_params = {
    'rs': 0.00706, 
    'ld': 0.0000965, 
    'lq': 0.0000965, 
    'jm': 0.02521,
    'kf': 0.005, 
    'lambda_m': 0.04748, 
    'p': 10, 
    'valor_mu': 0.95, 
    'velocidade_ref': 575.96,
    }

vehicle_params = {
    'mass': 240,
    'wheel_radius': 0.26,
    'wheel_mass': 5.0,
    'drag_coeff': 0.7789,
    'frontal_area': 0.68,
    'rolling_resistance': 0.015,
    'road_grade': 0,
    'L': 1.5,
    'h': 0.28,
    'dist_cg': 0.6,
    }

aero_params = {
    'has_wing': True,
    'lift_coeff_front': 1.0, 
    'area_front': 0.35,
    'lift_coeff_rear': 1.0,  
    'area_rear': 0.35,
    }

brake_params = {
    'RedP': 4,                              # Redução do pedal
    'a': 0.8,                               # Desaceleração [g]
    'psi': 0.48,                            # Distribuição de carga estática por eixo
    'μl': 0.45,                             # Atrito pastilha/disco
    'pi': np.pi,                            # Numero de pi
    'HCG': vehicle_params['h'],             # Altura do Centro de gravidade
    'μ': tire_params['tire_friction_coef'], # Atrito pneu/solo
    'FzF': vehicle_params['mass']*9.81*0.6, # Reação estática dianteira [N]
    'FzR': vehicle_params['mass']*9.81*0.4, # Reação estática traseira [N]
    'Rdp': vehicle_params['wheel_radius'],  # Raio do pneu
    'Dcm': 0.02,                            # Diâmetro cilindro mestre [m]
    'Dwc': 0.032,                           # Diâmetro cilindro da roda [m]
    'Npast': 2,                             # Pastilhas por disco
    'atrito_coeficiente': 0.35,             # Atrito da pastilha
    'red': 0.075,                           # Raio efetivo do disco [m]
    'Mt': vehicle_params['mass'],           # Massa total
    'm_wheel': vehicle_params['wheel_mass'],
    'm_tire': 10,                           # Massa do pneu
    'L': vehicle_params['L'],               # Entre-eixos
    'c_rr': vehicle_params['rolling_resistance']
}

battery = BatteryPack.BatteryPack(**BATTERY_PARAMS)
tire = Tire.Tire(**tire_params)
transmission = Transmission.Transmission(**transmission_params)
motor = Motor.Motor(
        rs=motor_params['rs'],
        ld=motor_params['ld'],
        lq=motor_params['lq'],
        jm=motor_params['jm'],
        kf=motor_params['kf'],
        lambda_m=motor_params['lambda_m'],
        p=motor_params['p'],
        valor_mu=motor_params['valor_mu'],
        speed_ref=motor_params['velocidade_ref'],
        max_current=323.0,  
    )
vehicle = Vehicle.Vehicle(**vehicle_params, **aero_params)
pedal = Pedal.Pedal(ganho=1.0)
pedal_tempos, pedal_throttle = Pedal.Pedal.perfil_suave(0.0, 3.0)
pedal.set_profile(pedal_tempos, pedal_throttle)
brake = BrakeSystem(brake_params)

sim = Simulation(
    motor=motor, 
    vehicle=vehicle, 
    transmission=transmission,
    battery=battery, 
    tire=tire,
    pedal=pedal,
    tmax=60.0, 
    dmax=75, 
    steps=12000,
    p_max_dc=80e3,
    )

sim.simulate()

power = sim.battery_voltage_hist * sim.battery_current_hist
energy = np.trapezoid(power,sim.tempo)
Wh = energy / 3600
energy_figure, sprint_energy = plot_sprint_energy(sim)

print(f'Energia consumida na aceleração: {Wh:.2f} Wh')

final_velocity = sim.vehicle_velocity[-1]

print(f'Velocidade até o freio: {final_velocity:.2f} m/s')

initial_angular_velocity = final_velocity / vehicle_params['wheel_radius'] 
pedal_force = 500
forca_frenagem, torque_ajustado, forca_f, torque_disco_freio, resistencia_rolamento, torque_resistencia_rolamento = brake.apply_brake(pedal_force=pedal_force)
print(f'Torque ajustado do freio: {torque_ajustado:.2f} N.m')

brake_force_from_discs = forca_f * 4

tire_friction_coef = tire_params['tire_friction_coef']

max_tire_braking_force = (
    tire_friction_coef
    * vehicle_params['mass']
    * 9.81
)

effective_braking_force = min(
    brake_force_from_discs,
    max_tire_braking_force
)

braking_force = effective_braking_force + resistencia_rolamento
deceleration = braking_force / vehicle_params['mass']

#Garante desaceleracao positiva
if deceleration <= 0:
    raise ValueError("A desaceleração precisa ser positiva.")

#contadores e parametros
dt = 0.001
velocity = final_velocity
time = 0.0
distance = 0.0

#listas
velocity_history = [velocity]
time_history = [time]
distance_history = [distance]

#acompanhar a evolução da velocidade durante a frenagem
while velocity > 0:
    step = min(dt, velocity / deceleration)

#formulas cinematicas  v = v0+at
    new_velocity = max(
        velocity - deceleration * step, 0.0
    )

    distance += (velocity + new_velocity) / 2 * step
    time += step
    velocity = new_velocity

    velocity_history.append(velocity)
    time_history.append(time)
    distance_history.append(distance)

print(f'Força de frenagem: {braking_force:.2f} N')
print(f'Desaceleração: {deceleration:.2f} m/s²')
print(f'Tempo de frenagem: {time:.3f} s')
print(f'Distância de frenagem: {distance:.2f} m')
print(f'Velocidade final: {velocity:.2f} m/s')

# esqueleto simulacao do endurance

endurance_distance = 22000  

#criacao de acumuladores 
total_distance = 0.0
total_energy = 0.0
total_time = 0.0
cycles = 0

#recuperar os valores da aceleracao
acceleration_distance = sim.vehicle_position[-1]
acceleration_time = sim.tempo[-1]

#construcao do ciclo
cycle_distance = acceleration_distance + distance
cycle_time = acceleration_time + time

#evitar ter distancia 0 e negativa
if cycle_distance <= 0:
    raise ValueError("A distância do ciclo precisa ser positiva.")

#loop da distancia 
while total_distance < endurance_distance:

    remaining_distance = endurance_distance - total_distance

    fraction = min(1.0, remaining_distance / cycle_distance)

#atualizacoes de distanica energia e tempo 
    total_distance += cycle_distance * fraction
    total_energy += Wh * fraction
    total_time += cycle_time * fraction

    cycles += 1


print(f"Distância total: {total_distance:.2f} m")
print(f"Ciclos executados: {cycles}")
print(f"Energia consumida: {total_energy:.2f} Wh")
print(f"Tempo total estimado: {total_time:.2f} s")

