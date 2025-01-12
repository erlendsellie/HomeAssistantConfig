async def correct_bad_readings():
    global decorated_functions

    decorated_functions = {}

    # fetch all sensors listed in the energy dashboard
    sensors = [k.get('stat_consumption') for k in hass.data['energy_manager'].data.get('device_consumption')]

    for sensor in sensors:
        log.debug(f"Setting up statistics corrector for {sensor}")
        @state_trigger(f"{sensor}")
        async def corrector(var_name=None, value=None):
            log.debug(f"Statistics corrector checking {var_name}")

            start_time = datetime.now() - timedelta(minutes=30)
            end_time = datetime.now()

            stats = _get_statistic(start_time, end_time, [var_name], "5minute", 'state')
            unit = state.getattr(var_name).get('unit_of_measurement')

            stat = [{'start': d.get('start'), 'value': float(d.get('state'))} for d in stats.get(var_name)]
            previous, last = stat[:-1], stat[-1]
            previous_values = [v.get('value') for v in previous]

            average = sum(previous_values) / len(previous_values)
            delta = abs(last.get('value') - average)

            #log.debug(f"Checking if delta ({delta}) is larger than avarage ({average})")

            if delta > average:
                log.debug(f"Delta to high for {var_name} | State: {last.get('value')}, Avarage value: {average}, Delta: {delta}")
                hass.data["recorder_instance"].async_adjust_statistics(statistic_id=var_name,
                                                                       start_time=last.get('start'),
                                                                       sum_adjustment=average,
                                                                       adjustment_unit=unit)

        decorated_functions[sensor] = corrector

    # this isn't needed afaik? or can we listen to an event regarding the energy manager, then this would be nice.
    for sensor in list(decorated_functions.keys()):
        if sensor not in sensors:
            del decorated_functions[sensor]