# ruff: noqa
""" The following code is based on
    https://github.com/talosh/flameTimewarpML/blob/main/pytorch/flameTimewarpML_inference.py

    It allows to "bake" or "plot" the curve values from a Timewarp saved setup.

    Speed animated timewarp are known to be less accurate, worth suggesting to the clients
    to avoid them.
"""
from copy import copy
import xml.etree.ElementTree as ET

APPROXIMATION_EPSILON = 1.0e-09
VERYSMALL = 1.0e-20
MAXIMUM_ITERATIONS = 100


class Timewarp():

    def bake_flame_tw_setup(self, tw_setup_string):
        # parses tw setup from flame and returns dictionary
        # with baked frame - value pairs
        
        def dictify(r, root=True):
            def string_to_value(s):
                if (s.find('-') <= 0) and s.replace('-', '', 1).isdigit():
                    return int(s)
                elif (s.find('-') <= 0) and (s.count('.') < 2) and \
                        (s.replace('-', '', 1).replace('.', '', 1).isdigit()):
                    return float(s)
                elif s == 'True':
                    return True
                elif s == 'False':
                    return False
                else:
                    return s

            if root:
                return {r.tag: dictify(r, False)}

            d = copy(r.attrib)
            if r.text:
                # d["_text"] = r.text
                d = r.text
            for x in r.findall('./*'):
                if x.tag not in d:
                    v = dictify(x, False)
                    if not isinstance (d, dict):
                        d = {}
                    if isinstance (v, str):
                        d[x.tag] = string_to_value(v)
                    else:
                        d[x.tag] = []
                if isinstance(d[x.tag], list):
                    d[x.tag].append(dictify(x, False))
            return d

        class FlameChannellInterpolator:
            # An attempt of a python rewrite of Julik Tarkhanov's original
            # Flame Channel Parsr written in Ruby.

            class ConstantSegment:
                def __init__(self, from_frame, to_frame, value):
                    self._mode = 'constant'
                    self.start_frame = from_frame
                    self.end_frame = to_frame
                    self.v1 = value

                def mode(self):
                    return self._mode

                def defines(self, frame):
                    return (frame < self.end_frame) and (frame >= self.start_frame)

                def value_at(self, frame):
                    return self.v1

            class LinearSegment(ConstantSegment):
                def __init__(self, from_frame, to_frame, value1, value2):
                    self.vint = (value2 - value1)
                    super().__init__(from_frame, to_frame, value1)
                    self._mode = 'linear'

                def value_at(self, frame):
                    on_t_interval = (frame - self.start_frame) / (self.end_frame - self.start_frame)
                    return self.v1 + (on_t_interval * self.vint)

            class HermiteSegment(LinearSegment):
                def __init__(self, from_frame, to_frame, value1, value2, tangent1, tangent2):
                    self.start_frame, self.end_frame = from_frame, to_frame
                    frame_interval = self.end_frame - self.start_frame
                    self._mode = 'hermite'

                    # self.HERMATRIX = [
                    #     [2, -3,  0,  1],
                    #     [-2, 3,  0,  0],
                    #     [1, -2,  1,  0],
                    #     [1, -1,  0,  0]
                    #  ].T

                    self.HERMATRIX = [
                        [2, -2,  1,  1],
                        [-3, 3,  -2,  -1],
                        [0, 0,  1,  0],
                        [1, 0,  0,  0]
                    ]

                    # Default tangents in flame are 0, so when we do None.to_f this is what we will get
                    # CC = {P1, P2, T1, T2}
                    p1, p2, t1, t2 = value1, value2, tangent1 * frame_interval, tangent2 * frame_interval
                    self.hermite = [p1, p2, t1, t2]
                    self.basis = self.dot_product_vector_matrix(self.HERMATRIX, self.hermite)

                @staticmethod
                def dot_product_vector_matrix(matrix, vector):
                    return [sum(a*b for a,b in zip(row, vector)) for row in matrix]

                @staticmethod
                def dot_product_vector_vector(vector1, vector2):
                    return sum(x*y for x, y in zip(vector1, vector2))

                def value_at(self, frame):
                    if frame == self.start_frame:
                        return self.hermite[0]

                    # Get the 0 < T < 1 interval we will interpolate on
                    # Q[frame_] = P[ ( frame - 149 ) / (time_to - time_from)]
                    t = (frame - self.start_frame) / (self.end_frame - self.start_frame)

                    # S[s_] = {s^3, s^2, s^1, s^0}
                    multipliers_vec = [t ** 3, t ** 2, t ** 1, t ** 0]

                    # P[s_] = S[s].h.CC
                    interpolated_scalar = self.dot_product_vector_vector(
                        self.basis, multipliers_vec
                    )
                    return interpolated_scalar

            class BezierSegment(LinearSegment):
                class Pt:
                    def __init__(self, x, y, tanx, tany):
                        self.x = x
                        self.y = y
                        self.tanx = tanx
                        self.tany = tany
                
                def __init__(self, x1, x2, y1, y2, t1x, t1y, t2x, t2y):
                    super().__init__(x1, x2, y1, y2)
                    self.a = self.Pt(x1, y1, t1x, t1y)
                    self.b = self.Pt(x2, y2, t2x, t2y)
                    self._mode = 'bezier'

                def value_at(self, frame):
                    if frame == self.start_frame:
                        return self.a.y
                    
                    t = self.approximate_t(frame, self.a.x, self.a.tanx, self.b.tanx, self.b.x)
                    vy = self.bezier(t, self.a.y, self.a.tany, self.b.tany, self.b.y)
                    return vy
                
                def bezier(self, t, a, b, c, d):
                    return a + (a*(-3) + b*3)*(t) + (a*3 - b*6 + c*3)*(t**2) + (-a + b*3 - c*3 + d)*(t**3)
                
                def clamp(self, value):
                    if value < 0:
                        return 0.0
                    elif value > 1:
                        return 1.0
                    else:
                        return value
                
                def approximate_t(self, atX, p0x, c0x, c1x, p1x):
                    if atX - p0x < VERYSMALL:
                        return 0.0
                    elif p1x - atX < VERYSMALL:
                        return 1.0

                    u, v = 0.0, 1.0
                    
                    for i in range(MAXIMUM_ITERATIONS):
                        a = (p0x + c0x) / 2.0
                        b = (c0x + c1x) / 2.0
                        c = (c1x + p1x) / 2.0
                        d = (a + b) / 2.0
                        e = (b + c) / 2.0
                        f = (d + e) / 2.0
                        
                        if abs(f - atX) < APPROXIMATION_EPSILON:
                            return self.clamp((u + v) * 0.5)
                        
                        if f < atX:
                            p0x = f
                            c0x = e
                            c1x = c
                            u = (u + v) / 2.0
                        else:
                            c0x = a
                            c1x = d
                            p1x = f
                            v = (u + v) / 2.0
                    
                    return self.clamp((u + v) / 2.0)

            class ConstantPrepolate(ConstantSegment):
                def __init__(self, to_frame, base_value):
                    super().__init__(float('-inf'), to_frame, base_value)
                    self._mode = 'ConstantPrepolate'

                def value_at(self, frame):
                    return self.v1

            class ConstantExtrapolate(ConstantSegment):
                def __init__(self, from_frame, base_value):
                    super().__init__(from_frame, float('inf'), base_value)
                    self._mode = 'ConstantExtrapolate'

                def value_at(self, frame):
                    return self.v1
                
            class LinearPrepolate(ConstantPrepolate):
                def __init__(self, to_frame, base_value, tangent):
                    self.tangent = float(tangent)
                    super().__init__(to_frame, base_value)
                    self._mode = 'LinearPrepolate'

                def value_at(self, frame):
                    frame_diff = (self.end_frame - frame)
                    return self.v1 + (self.tangent * frame_diff)
                
            class LinearExtrapolate(ConstantExtrapolate):
                def __init__(self, from_frame, base_value, tangent):
                    self.tangent = float(tangent)
                    super().__init__(from_frame, base_value)
                    self._mode = 'LinearExtrapolate'

                def value_at(self, frame):
                    frame_diff = (frame - self.start_frame)
                    return self.v1 + (self.tangent * frame_diff)

            class ConstantFunction(ConstantSegment):
                def __init__(self, value):
                    super().__init__(float('-inf'), float('inf'), value)
                    self._mode = 'ConstantFunction'

                def defines(self, frame):
                    return True

                def value_at(self, frame):
                    return self.v1

            def __init__(self, channel):
                self.segments = []
                self.extrap = channel.get('Extrap', 'constant')

                if channel.get('Size', 0) == 0:
                    self.segments = [FlameChannellInterpolator.ConstantFunction(channel.get('Value', 0))]
                elif channel.get('Size') == 1 and self.extrap == 'constant':
                    self.segments = [FlameChannellInterpolator.ConstantFunction(channel.get('Value', 0))]
                elif channel.get('Size') == 1 and self.extrap == 'linear':
                    kframes = channel.get('KFrames')
                    frame = list(kframes.keys())[0]
                    base_value = kframes[frame].get('Value')
                    left_tangent = kframes[frame].get('LHandle_dY') / kframes[frame].get('LHandle_dX') * -1
                    right_tangent = kframes[frame].get('RHandle_dY') / kframes[frame].get('RHandle_dX')
                    self.segments = [
                        FlameChannellInterpolator.LinearPrepolate(frame, base_value, left_tangent),
                        FlameChannellInterpolator.LinearExtrapolate(frame, base_value, right_tangent)
                    ]
                else:
                    self.segments = self.create_segments_from_channel(channel)

            def sample_at(self, frame):
                if self.extrap == 'cycle':
                    return self.sample_from_segments(self.frame_number_in_cycle(frame))
                elif self.extrap == 'revcycle':
                    return self.sample_from_segments(self.frame_number_in_revcycle(frame))
                else:
                    return self.sample_from_segments(frame)

            def first_defined_frame(self):
                first_f = self.segments[0].end_frame
                if first_f == float('-inf'):
                    return 1
                return first_f

            def last_defined_frame(self):
                last_f = self.segments[-1].start_frame
                if last_f == float('inf'):
                    return 100
                return last_f

            def frame_number_in_revcycle(self, frame):
                animated_across = self.last_defined_frame() - self.first_defined_frame()
                offset = abs(frame - self.first_defined_frame())
                absolute_unit = offset % animated_across
                cycles = offset // animated_across
                if cycles % 2 == 0:
                    return self.first_defined_frame() + absolute_unit
                else:
                    return self.last_defined_frame() - absolute_unit

            def frame_number_in_cycle(self, frame):
                animated_across = self.last_defined_frame() - self.first_defined_frame()
                offset = frame - self.first_defined_frame()
                modulo = offset % animated_across
                return self.first_defined_frame() + modulo

            def create_segments_from_channel(self, channel):
                kframes = channel.get('KFrames')
                index_frames = list(kframes.keys())
                # First the prepolating segment
                segments = [self.pick_prepolation(channel.get('Extrap', 'constant'), kframes[index_frames[0]], kframes[index_frames[1]])]

                # Then all the intermediate segments, one segment between each pair of keys
                for index, key in enumerate(index_frames[:-1]):
                    segments.append(self.key_pair_to_segment(kframes[key], kframes[index_frames[index + 1]]))

                # and the extrapolator
                segments.append(self.pick_extrapolation(channel.get('Extrap', 'constant'), kframes[index_frames[-2]], kframes[index_frames[-1]]))
                return segments

            def sample_from_segments(self, at_frame):
                for segment in self.segments:
                    if segment.defines(at_frame):
                        return segment.value_at(at_frame)
                raise ValueError(f'No segment on this curve that can interpolate the value at {at_frame}')
            
            def segment_mode(self, at_frame):
                for segment in self.segments:
                    if segment.defines(at_frame):
                        return segment.mode()
                raise ValueError(f'No segment on this curve that can interpolate the value at {at_frame}')
            
            def get_segment(self, at_frame):
                for segment in self.segments:
                    if segment.defines(at_frame):
                        return segment
                raise ValueError(f'No segment on this curve that can interpolate the value at {at_frame}')

            def pick_prepolation(self, extrap_symbol, first_key, second_key):
                if extrap_symbol == 'linear' and second_key:
                    if first_key.get('CurveMode') != 'linear':
                        first_key_left_slope = first_key.get('LHandle_dY') / first_key.get('LHandle_dX') * -1
                        return FlameChannellInterpolator.LinearPrepolate(
                            first_key.get('Frame'), 
                            first_key.get('Value'), 
                            first_key_left_slope)
                    else:
                        # For linear keys the tangent actually does not do anything, so we need to look a frame
                        # ahead and compute the increment
                        increment = (second_key.get('Value') - first_key.get('Value')) / (second_key.get('Frame') - first_key.get('Frame'))
                        return FlameChannellInterpolator.LinearPrepolate(first_key.get('Frame'), first_key.get('Value'), increment)
                else:
                    return FlameChannellInterpolator.ConstantPrepolate(first_key.get('Frame'), first_key.get('Value'))
            
            def pick_extrapolation(self, extrap_symbol, previous_key, last_key):
                if extrap_symbol != 'constant':
                    if previous_key and (last_key.get('CurveMode')  == 'linear' or last_key.get('CurveOrder')  == 'linear'):
                        # For linear keys the tangent actually does not do anything, so we need to look a frame
                        # ahead and compute the increment
                        increment = (last_key.get('Value') - previous_key.get('Value')) / (last_key.get('Frame') - previous_key.get('Frame'))
                        return FlameChannellInterpolator.LinearExtrapolate(last_key.get('Frame'), last_key.get('Value'), increment)
                    else:
                        last_key_right_slope = last_key.get('LHandle_dY') / last_key.get('LHandle_dX')
                        return FlameChannellInterpolator.LinearExtrapolate(last_key.get('Frame'), last_key.get('Value'), last_key_right_slope)
                else:
                    return FlameChannellInterpolator.ConstantExtrapolate(last_key.get('Frame'), last_key.get('Value'))

            def key_pair_to_segment(self, key, next_key):
                key_left_tangent = key.get('LHandle_dY') / key.get('LHandle_dX') * -1
                key_right_tangent = key.get('RHandle_dY') / key.get('RHandle_dX')
                next_key_left_tangent = next_key.get('LHandle_dY') / next_key.get('LHandle_dX') # * -1
                next_key_right_tangent = next_key.get('RHandle_dY') / next_key.get('RHandle_dX')

                if key.get('CurveMode') == 'bezier':
                    return FlameChannellInterpolator.BezierSegment(
                        key.get('Frame'), 
                        next_key.get('Frame'),
                        key.get('Value'), 
                        next_key.get('Value'),
                        float(key.get('Frame')) + float(key.get('RHandle_dX')), 
                        float(key.get('Value')) + float(key.get('RHandle_dY')),
                        float(next_key.get('Frame')) + float(next_key.get('LHandle_dX')),
                        float(next_key.get('Value')) + float(next_key.get('LHandle_dY'))
                        )
                
                elif (key.get('CurveMode') in ['natural', 'hermite']) and (key.get('CurveOrder') == 'cubic'):
                    return FlameChannellInterpolator.HermiteSegment(
                        key.get('Frame'), 
                        next_key.get('Frame'), 
                        key.get('Value'), 
                        next_key.get('Value'),
                        key_right_tangent, 
                        next_key_left_tangent
                        )
                elif (key.get('CurveMode') in ['natural', 'hermite']) and (key.get('CurveOrder') == 'quartic'):
                    return FlameChannellInterpolator.HermiteSegment(
                        key.get('Frame'), 
                        next_key.get('Frame'), 
                        key.get('Value'), 
                        next_key.get('Value'),
                        key_right_tangent, 
                        next_key_left_tangent
                        )
                elif key.get('CurveMode') == 'constant':
                    return FlameChannellInterpolator.ConstantSegment(
                        key.get('Frame'), 
                        next_key.get('Frame'), 
                        key.get('Value')
                        )
                else:  # Linear and safe
                    return FlameChannellInterpolator.LinearSegment(
                        key.get('Frame'), 
                        next_key.get('Frame'), 
                        key.get('Value'), 
                        next_key.get('Value')
                        )

        def approximate_speed_curve(tw_setup_string, start, end, tw_channel):
            from xml.dom import minidom
            xml = minidom.parseString(tw_setup_string)  
            tw_speed_timing = {}
            TW_SpeedTiming = xml.getElementsByTagName('TW_SpeedTiming')
            keys = TW_SpeedTiming[0].getElementsByTagName('Key')
            for key in keys:
                index = key.getAttribute('Index') 
                frame = key.getElementsByTagName('Frame')
                if frame:
                    frame = (frame[0].firstChild.nodeValue)
                value = key.getElementsByTagName('Value')
                if value:
                    value = (value[0].firstChild.nodeValue)
                tw_speed_timing[int(index)] = {'frame': int(frame), 'value': float(value)}

            if tw_speed_timing[0]['frame'] > start:
                # we need to extrapolate backwards from the first 
                # keyframe in SpeedTiming channel

                anchor_frame_value = tw_speed_timing[0]['value']
                for frame_number in range(tw_speed_timing[0]['frame'] - 1, start - 1, -1):
                    if frame_number + 1 not in tw_channel.keys() or frame_number not in tw_channel.keys():
                        step_back = tw_channel[min(list(tw_channel.keys()))] / 100
                    else:
                        step_back = (tw_channel[frame_number + 1] + tw_channel[frame_number]) / 200
                    frame_value_map[frame_number] = anchor_frame_value - step_back
                    anchor_frame_value = frame_value_map[frame_number]

            # build up frame values between keyframes of SpeedTiming channel
            for key_frame_index in range(0, len(tw_speed_timing.keys()) - 1):
                # The value from my gess algo is close to the one in flame but not exact
                # and error is accumulated. SO quick and dirty way is to do forward
                # and backward pass and mix them rationally

                range_start = tw_speed_timing[key_frame_index]['frame']
                range_end = tw_speed_timing[key_frame_index + 1]['frame']
                
                if range_end == range_start + 1:
                # keyframes on next frames, no need to interpolate
                    frame_value_map[range_start] = tw_speed_timing[key_frame_index]['value']
                    frame_value_map[range_end] = tw_speed_timing[key_frame_index + 1]['value']
                    continue

                forward_pass = {}
                anchor_frame_value = tw_speed_timing[key_frame_index]['value']
                forward_pass[range_start] = anchor_frame_value

                for frame_number in range(range_start + 1, range_end):
                    if frame_number + 1 not in tw_channel.keys() or frame_number not in tw_channel.keys():
                        step = tw_channel[max(list(tw_channel.keys()))] / 100
                    else:
                        step = (tw_channel[frame_number] + tw_channel[frame_number + 1]) / 200
                    forward_pass[frame_number] = anchor_frame_value + step
                    anchor_frame_value = forward_pass[frame_number]
                forward_pass[range_end] = tw_speed_timing[key_frame_index + 1]['value']
                
                backward_pass = {}
                anchor_frame_value = tw_speed_timing[key_frame_index + 1]['value']
                backward_pass[range_end] = anchor_frame_value
                
                for frame_number in range(range_end - 1, range_start -1, -1):
                    if frame_number + 1 not in tw_channel.keys() or frame_number not in tw_channel.keys():
                        step_back = tw_channel[min(list(tw_channel.keys()))] / 100
                    else:
                        step_back = (tw_channel[frame_number + 1] + tw_channel[frame_number]) / 200
                    backward_pass[frame_number] = anchor_frame_value - step_back
                    anchor_frame_value = backward_pass[frame_number]
                
                backward_pass[range_start] = tw_speed_timing[key_frame_index]['value']

                def hermite_curve(t):
                    P0, P1 = 0, 1
                    T0, T1 = 0, 0
                    h00 = 2*t**3 - 3*t**2 + 1  # Compute basis function 1
                    h10 = t**3 - 2*t**2 + t    # Compute basis function 2
                    h01 = -2*t**3 + 3*t**2     # Compute basis function 3
                    h11 = t**3 - t**2          # Compute basis function 4

                    return h00 * P0 + h10 * T0 + h01 * P1 + h11 * T1


                work_range = list(forward_pass.keys())
                ratio = 0
                rstep = 1 / len(work_range)
                for frame_number in sorted(work_range):
                    frame_value_map[frame_number] = forward_pass[frame_number] * (1 - hermite_curve(ratio)) + backward_pass[frame_number] * hermite_curve(ratio)
                    ratio += rstep

            last_key_index = list(sorted(tw_speed_timing.keys()))[-1]
            if tw_speed_timing[last_key_index]['frame'] < end:
                # we need to extrapolate further on from the 
                # last keyframe in SpeedTiming channel
                anchor_frame_value = tw_speed_timing[last_key_index]['value']
                frame_value_map[tw_speed_timing[last_key_index]['frame']] = anchor_frame_value

                for frame_number in range(tw_speed_timing[last_key_index]['frame'] + 1, end + 1):
                    if frame_number + 1 not in tw_channel.keys() or frame_number not in tw_channel.keys():
                        step = tw_channel[max(list(tw_channel.keys()))] / 100
                    else:
                        step = (tw_channel[frame_number] + tw_channel[frame_number + 1]) / 200
                    frame_value_map[frame_number] = anchor_frame_value + step
                    anchor_frame_value = frame_value_map[frame_number]

            return frame_value_map

        tw_setup_xml = ET.fromstring(tw_setup_string)
        tw_setup = dictify(tw_setup_xml)

        start_frame = int(tw_setup['Setup']['Base'][0]['Range'][0]['Start'])
        end_frame = int(tw_setup['Setup']['Base'][0]['Range'][0]['End'])

        TW_RetimerMode = tw_setup['Setup']['State'][0]['TW_RetimerMode']

        frame_value_map = {}

        if TW_RetimerMode == 1:
            # 'Timing' channel is enough
            tw_channel = 'TW_Timing'
            channel = tw_setup['Setup']['State'][0][tw_channel][0]['Channel'][0]
            if 'KFrames' in channel.keys():
                channel['KFrames'] = {x['Frame']: x for x in sorted(channel['KFrames'][0]['Key'], key=lambda d: d['Value'])}
            interpolator = FlameChannellInterpolator(channel)
            for frame_number in range (start_frame, end_frame+1):
                frame_value_map[frame_number] = round(interpolator.sample_at(frame_number), 4)
            return frame_value_map

        else:
            # speed - based timewarp seem to
            # work in a different way
            # depending on a segment mode

            tw_channel = 'TW_Speed'
            channel = tw_setup['Setup']['State'][0][tw_channel][0]['Channel'][0]
            if 'KFrames' in channel.keys():
                channel['KFrames'] = {x['Frame']: x for x in sorted(channel['KFrames'][0]['Key'], key=lambda d: d['Value'])}
            speed_channel = dict(channel)
            tw_channel = 'TW_SpeedTiming'
            channel = tw_setup['Setup']['State'][0][tw_channel][0]['Channel'][0]
            if 'KFrames' in channel.keys():
                channel['KFrames'] = {x['Frame']: x for x in sorted(channel['KFrames'][0]['Key'], key=lambda d: d['Value'])}
            speed_timing_channel = dict(channel)

            if 'quartic' in tw_setup_string:
                speed_interpolator = FlameChannellInterpolator(speed_channel)
                interpolated_speed_channel = {}
                for frame_number in range (start_frame, end_frame+1):
                    interpolated_speed_channel[frame_number] = round(speed_interpolator.sample_at(frame_number), 4)

                #return approximate_speed_curve(tw_setup_string, self.record_in, self.record_out, interpolated_speed_channel)
                return approximate_speed_curve(tw_setup_string, start_frame, end_frame, interpolated_speed_channel)

            timing_interpolator = FlameChannellInterpolator(speed_timing_channel)

            for frame_number in range (start_frame, end_frame+1):
                frame_value_map[frame_number] = round(timing_interpolator.sample_at(frame_number), 4)
                    
        return frame_value_map
