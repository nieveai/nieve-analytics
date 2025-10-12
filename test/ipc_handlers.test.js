const { ipcMain } = require('electron');
const path = require('path');
const crypto = require('crypto');

// Mock appState and pythonManager
const appState = {
    dataSources: {
        'ds1': {
            id: 'ds1',
            name: 'test_data',
            type: 'csv',
            config: { filePath: 'test.csv' },
            visualizations: [],
            analyses: [],
            transforms: []
        }
    },
    settings: {
        models: [{
            id: 'model1',
            name: 'Default Model',
            provider: 'gemini',
            apiKey: 'fake-key',
            modelName: 'gemini-2.5-flash'
        }],
        activeModelId: 'model1'
    }
};

const pythonManager = {
    send: jest.fn(),
    readyPromise: Promise.resolve(),
    handleResponses: () => {}
};

// Mock crypto.randomUUID
crypto.randomUUID = jest.fn(() => 'mock-uuid');

// Mock fs for saveState and loadState
const fs = require('fs');
jest.mock('fs', () => ({
    existsSync: jest.fn(() => true),
    readFileSync: jest.fn(() => JSON.stringify(appState)),
    writeFileSync: jest.fn(),
    mkdirSync: jest.fn(),
    appendFileSync: jest.fn()
}));

// Mock electron dialog
const { EventEmitter } = require('events');
const handlers = new Map();
const mockIpcMain = {
    ...new EventEmitter(),
    handle: (channel, handler) => {
        handlers.set(channel, handler);
    },
    invoke: (channel, ...args) => {
        const handler = handlers.get(channel);
        if (!handler) return Promise.reject(new Error(`No handler for ${channel}`));
        return handler({ sender: { send: jest.fn() } }, ...args);
    }
};

jest.mock('electron', () => ({
    dialog: {
        showOpenDialog: jest.fn(),
        showSaveDialog: jest.fn(),
        showErrorBox: jest.fn()
    },
    ipcMain: mockIpcMain,
    app: {
        whenReady: jest.fn(() => Promise.resolve()),
        on: jest.fn()
    },
    BrowserWindow: jest.fn(),
    Menu: jest.fn(),
    clipboard: jest.fn(),
    nativeImage: jest.fn()
}));

const { ipcMain } = require('electron');

// Load the main process file after mocks are set up
require('../index.js');

describe('ipcMain analyze handler', () => {
    beforeEach(() => {
        // Reset mocks before each test
        pythonManager.send.mockClear();
        fs.writeFileSync.mockClear();
        crypto.randomUUID.mockClear();
        crypto.randomUUID.mockImplementation(() => 'mock-uuid'); // Ensure consistent UUID for tests
    });

    test('should call pythonManager.send with correct arguments for analyze without transformationId', async () => {
        pythonManager.send.mockResolvedValueOnce({ success: true, payload: { resultData: 10, resultType: 'int', generatedCode: 'df.sum()' } });

        const mockEvent = {};
        const dataSourceId = 'ds1';
        const command = 'sum of col1';

        await ipcMain.emit('analyze', mockEvent, dataSourceId, command);

        expect(pythonManager.send).toHaveBeenCalledTimes(1);
        expect(pythonManager.send).toHaveBeenCalledWith(
            'analyze',
            {
                data_source: appState.dataSources[dataSourceId],
                command: command,
                transformation_id: null
            }
        );
        expect(fs.writeFileSync).toHaveBeenCalledTimes(1);
    });

    test('should call pythonManager.send with correct arguments for analyze with transformationId', async () => {
        pythonManager.send.mockResolvedValueOnce({ success: true, payload: { resultData: 60, resultType: 'int', generatedCode: 'df.sum()' } });

        const mockEvent = {};
        const dataSourceId = 'ds1';
        const command = 'sum of transformed col1';
        const transformationId = 'tr1';

        await ipcMain.emit('analyze', mockEvent, dataSourceId, command, transformationId);

        expect(pythonManager.send).toHaveBeenCalledTimes(1);
        expect(pythonManager.send).toHaveBeenCalledWith(
            'analyze',
            {
                data_source: appState.dataSources[dataSourceId],
                command: command,
                transformation_id: transformationId
            }
        );
        expect(fs.writeFileSync).toHaveBeenCalledTimes(1);
    });

    test('should handle python error correctly', async () => {
        const pyError = { __pyError: true, type: 'CodeExecutionError', message: 'Error executing code', code: 'bad_code' };
        pythonManager.send.mockResolvedValueOnce({ success: false, error: pyError });

        const mockEvent = {};
        const dataSourceId = 'ds1';
        const command = 'bad command';

        const result = await ipcMain.emit('analyze', mockEvent, dataSourceId, command);

        expect(pythonManager.send).toHaveBeenCalledTimes(1);
        expect(result[0]).toEqual(expect.objectContaining({
            __pyError: true,
            type: 'CodeExecutionError',
            message: 'Error executing code',
            code: 'bad_code',
            id: 'mock-uuid',
            command: 'bad command'
        }));
        expect(fs.writeFileSync).toHaveBeenCalledTimes(1);
    });
});
