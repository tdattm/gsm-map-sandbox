"""Read-only stdlib resource telemetry; no process termination or new dependencies."""
import ctypes
import os
import platform
import subprocess
import threading
import time


def memory():
    if os.name == 'nt':
        class Status(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)]+[(n, ctypes.c_ulonglong) for n in
                ('totalPhysical', 'availablePhysical', 'totalPageFile', 'availablePageFile', 'totalVirtual', 'availableVirtual', 'availableExtendedVirtual')]
        status = Status()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError('GlobalMemoryStatusEx failed')
        class Counters(ctypes.Structure):
            _fields_ = [('cb', ctypes.c_ulong), ('pageFaultCount', ctypes.c_ulong)]+[(n, ctypes.c_size_t) for n in
                ('peakWorkingSet', 'workingSet', 'quotaPeakPagedPool', 'quotaPagedPool', 'quotaPeakNonPagedPool', 'quotaNonPagedPool', 'pagefile', 'peakPagefile')]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        process_memory = ctypes.windll.psapi.GetProcessMemoryInfo
        process_memory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if not process_memory(handle, ctypes.byref(counters), counters.cb):
            raise OSError('GetProcessMemoryInfo failed')
        return {'totalPhysicalBytes': status.totalPhysical, 'availablePhysicalBytes': status.availablePhysical,
            'processRssBytes': counters.workingSet, 'processPeakRssBytes': counters.peakWorkingSet,
            'processPagefileBytes': counters.pagefile}
    values = {}
    with open('/proc/meminfo', encoding='ascii') as stream:
        for line in stream:
            key, value = line.split(':', 1)
            values[key] = int(value.strip().split()[0])*1024
    import resource
    usage = resource.getrusage(resource.RUSAGE_SELF)
    with open('/proc/self/statm', encoding='ascii') as stream:
        rss = int(stream.read().split()[1])*os.sysconf('SC_PAGE_SIZE')
    return {'totalPhysicalBytes': values['MemTotal'], 'availablePhysicalBytes': values['MemAvailable'],
        'processRssBytes': rss, 'processPeakRssBytes': usage.ru_maxrss*1024}


def environment():
    result = {'platform': platform.platform(), 'python': platform.python_version(), 'cpuCount': os.cpu_count(),
        'processor': platform.processor(), 'memory': memory()}
    try:
        result['dockerStats'] = subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{json .}}'],
            capture_output=True, text=True, timeout=15).stdout.strip().splitlines()
    except (OSError, subprocess.TimeoutExpired) as exc:
        result['dockerStatsUnavailable'] = str(exc)
    if os.name == 'nt':
        try:
            result['hardware'] = subprocess.run(['powershell', '-NoProfile', '-Command',
                'Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json -Compress; Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json -Compress'],
                capture_output=True, text=True, timeout=15).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return result


class Monitor:
    def __init__(self, interval=.05):
        self.interval = interval
        self.samples = []
        self.stop = threading.Event()

    def __enter__(self):
        self.samples.append(memory())
        def poll():
            while not self.stop.wait(self.interval):
                self.samples.append(memory())
        self.thread = threading.Thread(target=poll, daemon=True)
        self.thread.start()
        self.wall, self.cpu = time.perf_counter(), time.process_time()
        return self

    def __exit__(self, *_):
        self.wall = time.perf_counter()-self.wall
        self.cpu = time.process_time()-self.cpu
        self.stop.set()
        self.thread.join()
        self.samples.append(memory())

    def result(self):
        return {'wallSeconds': self.wall, 'cpuSeconds': self.cpu,
            'cpuPercentOneCore': self.cpu/self.wall*100,
            'peakRssBytesSampled': max(s['processRssBytes'] for s in self.samples),
            'processPeakRssBytes': max(s['processPeakRssBytes'] for s in self.samples),
            'minimumAvailablePhysicalBytes': min(s['availablePhysicalBytes'] for s in self.samples),
            'sampleIntervalSeconds': self.interval, 'sampleCount': len(self.samples)}


def require_headroom(minimum_gib=2.):
    current = memory()
    if current['availablePhysicalBytes'] < minimum_gib*1024**3:
        raise RuntimeError(f'RESOURCE_STOP: available RAM {current["availablePhysicalBytes"]/1024**3:.2f} GiB < {minimum_gib} GiB')
    return current
