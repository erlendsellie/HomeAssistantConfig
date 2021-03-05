@service
def hello_world(action=None, id=None):
    """hello_world example using pyscript."""
    log.info(f"hello world: got action {action} id {id}")    
    if action == 'turn_on' and id is not None:
        light.turn_on(entity_id=id, brightness=255)
    if action == 'turn_off' and id is not None:
        light.turn_off(entity_id=id)

@state_trigger("input_boolean.testbutton == 'on' or input_boolean.testbutton == 'off'")
# @time_active("range(sunset - 20min, sunrise + 15min)")
def togglePlay():
    if input_boolean.testbutton == 'off':
        light.turn_off(entity_id="light.play")
    if input_boolean.testbutton == 'on':
        light.turn_on(entity_id="light.play")
    task.sleep(300)
    if binary_sensor.motion_downstairs_office == 'off':
        light.turn_off(light.play)