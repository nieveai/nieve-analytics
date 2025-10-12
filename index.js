const { app, BrowserWindow, ipcMain, dialog, Menu, clipboard, nativeImage } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');
const crypto = require('crypto');
const zmq = require('zeromq');

// --- State Management ---
const STATE_DIR = path.join(os.homedir(), '.nieve-ai');
const STATE_FILE = path.join(STATE_DIR, 'state.json');
let appState;

// --- Python Process Manager ---
class PythonManager {
    constructor() {
        this.socket = new zmq.Request();
        this.socket.connect('tcp://127.0.0.1:5555');
        this.requests = new Map();
        this.readyPromise = this.startProcess();
        console.log("Python process starting...");
    }    
        

    startProcess() {
        return new Promise((resolve, reject) => {
            const pythonExecutable = process.platform === 'win32'
                ? path.join(__dirname, '.venv', 'Scripts', 'python.exe')
                : path.join(__dirname, '.venv', 'bin', 'python');
            
            this.pythonProcess = spawn(pythonExecutable, ['-u', 'main.py']);

            this.pythonProcess.stdout.on('data', (data) => {
                const message = data.toString();
                logError(`Python stdout: ${message}`); // Log all stdout for debugging
                if (message.trim() === 'PYTHON_ZMQ_READY') {
                    console.log('Python ZMQ is ready.');
                    resolve(); // Signal that the process is ready
                }
            });

            this.pythonProcess.stderr.on('data', (data) => {
                logError(`Python Process: ${data}`);
            });

            this.pythonProcess.on('close', (code) => {
                logError(`Python process exited with code ${code}`);
                this.pythonProcess = null;
                this.requests.forEach(({ reject: reqReject }, requestId) => {
                    reqReject(new Error(`Python process exited with code ${code}`));
                    this.requests.delete(requestId);
                });
                // Reject the readiness promise if the process exits before it's ready
                reject(new Error(`Python process exited with code ${code} before it was ready.`));
            });
        });
    }

    async handleResponses() {
        for await (const [msg] of this.socket) {
            try {
                // console.log(`Received ZMQ message: ${msg.toString()}`);
                const response = JSON.parse(msg.toString());
                const { requestId, success, payload, error } = response;
                                if (this.requests.has(requestId)) {
                                    const { resolve, reject } = this.requests.get(requestId);
                                    if (success) {
                                        resolve({ success: true, payload: payload });
                                    } else {
                                        resolve({ success: false, error: error });
                                    }
                                    this.requests.delete(requestId);
                                }
                            } catch (e) {
                                logError(`Error parsing JSON from Python: ${msg.toString()}`);
                                // If we can't parse the response, we don't know which request it was for.
                                // To prevent the app from hanging, we reject all pending requests.
                                const errorMessage = `Invalid JSON response from Python: ${msg.toString()}`;
                                this.requests.forEach(({ reject: reqReject }, requestId) => {
                                    reqReject(new Error(errorMessage));
                                    this.requests.delete(requestId);
                                });
                            }        }
    }

    async send(command, payload) {
        await this.readyPromise; // Wait for the Python process to be ready
        if (!this.pythonProcess) {
            throw new Error("Python process is not running.");
        }
        const requestId = crypto.randomUUID();
        const request = { command, payload, requestId };
        console.log(`Sending ZMQ request: ${requestId}`);
        await this.socket.send(JSON.stringify(request));
        return new Promise((resolve, reject) => {
            this.requests.set(requestId, { resolve, reject });
        });
    }
}

let pythonManager;


// Basic encryption for the API key.
const ALGORITHM = 'aes-256-cbc';
const ENCRYPTION_KEY = crypto.scryptSync('nieve-ai-key', 'salt', 32);
const IV = Buffer.alloc(16, 0);

function encrypt(text) {
    const cipher = crypto.createCipheriv(ALGORITHM, ENCRYPTION_KEY, IV);
    let encrypted = cipher.update(text, 'utf8', 'hex');
    encrypted += cipher.final('hex');
    return encrypted;
}

function decrypt(text) {
    const decipher = crypto.createDecipheriv(ALGORITHM, ENCRYPTION_KEY, IV);
    let decrypted = decipher.update(text, 'hex', 'utf8');
    decrypted += decipher.final('utf8');
    return decrypted;
}

function saveState() {
    try {
        if (!fs.existsSync(STATE_DIR)) {
            fs.mkdirSync(STATE_DIR);
        }
        const stateToSave = JSON.parse(JSON.stringify(appState)); // Deep copy

        stateToSave.settings.models.forEach(model => {
          if (model.apiKey) {
              model.apiKey = encrypt(model.apiKey);
          }
        });
      
        fs.writeFileSync(STATE_FILE, JSON.stringify(stateToSave, null, 2));
    } catch (error) {
        logError(error);
    }
}

function loadState() {
    console.log(`INFO: loading state from ${STATE_FILE}`);
    try {
        if (fs.existsSync(STATE_FILE)) {
            const rawData = fs.readFileSync(STATE_FILE);
            let state = JSON.parse(rawData);
            // Start migration to multiple models

            if (!state.settings.models || !Array.isArray(state.settings.models)) {
                state.settings.models = [];
            }

            if (state.settings.models.length === 0) {
                state.settings.models.push({
                    id: crypto.randomUUID(),
                    name: 'Default Model',
                    provider: 'gemini',
                    apiKey: '',
                    modelName: 'gemini-2.5-flash'
                });
            }

            if (!state.settings.activeModelId && state.settings.models.length > 0) {
                state.settings.activeModelId = state.settings.models[0].id;
            }

            // End migration
            // Decrypt API keys for all models
            state.settings.models.forEach(model => {
                if (model.apiKey) {
                    try {
                        model.apiKey = decrypt(model.apiKey);
                    } catch (e) {
                        logError(`Failed to decrypt API key for model ${model.name}. It might be corrupted.`);
                        model.apiKey = ''; // Reset corrupted key
                    }
                }
            });

            console.log(`INFO: State loaded with ${Object.keys(state.dataSources).length} data sources and ${state.settings.models.length} models.`);
            return state;
        }

    }
    catch (error) {
        logError(error);
    }

    

    // Return a default state if file doesn't exist or an error occurs

    const defaultModelId = crypto.randomUUID();

    return { 

        settings: { 

            models: [{

                id: defaultModelId,

                name: 'Default Model',

                provider: 'gemini',

                apiKey: '',

                modelName: 'gemini-2.5-flash'

            }],

            activeModelId: defaultModelId

        }, 

        dataSources: {} 

    };

}

function logError(error) {
  const logMessage = `[${new Date().toISOString()}] ${error.toString()}\n`;
  fs.appendFileSync('app.log', logMessage);
}

function createWindow () {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });
  win.loadFile('index.html');
}

app.whenReady().then(async () => {
    appState = loadState();
    pythonManager = new PythonManager();
    pythonManager.handleResponses();
    createWindow();
    // Initialize the model client in the Python backend
    const activeModel = appState.settings.models.find(m => m.id === appState.settings.activeModelId);
    if (activeModel) {
        // console.log(`DEBUG: ${activeModel.apiKey}`);
        await pythonManager.send('initialize_model_client', {
            model_provider: activeModel.provider,
            model_name: activeModel.modelName,
            api_key: activeModel.apiKey,
            base_url: activeModel.baseUrl
        });
    }
});

// --- IPC Handlers ---

ipcMain.handle('get-initial-state', () => {
    console.info('initializaiton ...');
    return appState;
});

ipcMain.handle('save-settings', async (event, settings) => {
    // Encrypt API keys before saving
    // const settingsToSave = JSON.parse(JSON.stringify(settings)); // Deep copy
    
    appState.settings = settings;
    saveState();

    // Re-initialize the model client in the Python backend with the new active model settings
    const activeModel = appState.settings.models.find(m => m.id === appState.settings.activeModelId);
    if (activeModel) {
        await pythonManager.send('initialize_model_client', {
            model_provider: activeModel.provider,
            model_name: activeModel.modelName,
            api_key: activeModel.apiKey,
            base_url: activeModel.baseUrl
        });
    }
    return { success: true };
});

ipcMain.handle('open-file', async () => {
    const { canceled, filePaths } = await dialog.showOpenDialog({
        properties: ['openFile'],
        filters: [{ name: 'CSV Files', extensions: ['csv'] }]
    });

    if (canceled || filePaths.length === 0) {
        return { newDataSource: null };
    }

    const filePath = filePaths[0];
    const fileName = path.basename(filePath);

    const existingSource = Object.values(appState.dataSources).find(ds => ds.config.filePath === filePath);
    if (existingSource) {
        return { newDataSource: null, existingId: existingSource.id };
    }

    try {
        const dataSourceId = crypto.randomUUID();
        const newDataSource = {
            id: dataSourceId,
            name: fileName,
            type: 'csv',
            config: { filePath },
            createdAt: new Date().toISOString(),
            visualizations: [],
            analyses: [],
            transforms: []
        };
        const previewData = await pythonManager.send('preview_data', { data_source: newDataSource });
        newDataSource.previewData = previewData.payload;
        appState.dataSources[dataSourceId] = newDataSource;
        saveState();
        return { newDataSource };
    } catch (error) {
        logError(error);
        throw error;
    }
});

ipcMain.handle('open-sqlite-file', async () => {
    const { canceled, filePaths } = await dialog.showOpenDialog({
        properties: ['openFile'],
        filters: [{ name: 'SQLite DB', extensions: ['db', 'sqlite', 'sqlite3'] }]
    });

    if (canceled || filePaths.length === 0) {
        return null;
    }

    const filePath = filePaths[0];
    try {
        const result = await pythonManager.send('get_sqlite_schema', { file_path: filePath });
        const schema = result.payload;
        return { filePath, schema };
    } catch (error) {
        logError(error);
        throw error;
    }
});

ipcMain.handle('refresh-data-source', async (event, dataSourceId) => {
    try {
        // Step 1: Invalidate the cache in the Python backend
        await pythonManager.send('invalidate_cache', { data_source_id: dataSourceId });

        // Step 2: Re-fetch the preview data
        const dataSource = getDataSourceConfig(appState.dataSources[dataSourceId]);
        if (!dataSource) {
            throw new Error('Data source not found.');
        }

        const result = await pythonManager.send('preview_data', { data_source: dataSource });
        // Step 3: Update the state and save it
        if (result.success) {
          dataSource.previewData = result.payload;
          saveState();

        // Step 4: Return the new preview data to the renderer
          return result.payload;
        } else {
          throw new Error("Failed to retrieve preview data");
        }
        
    } catch (error) {
        logError(error);
        throw error;
    }
});

ipcMain.handle('load-sqlite-data', async (event, filePath, query, sourceName) => {
    try {
        const dataSourceId = crypto.randomUUID();
        const newDataSource = {
            id: dataSourceId,
            name: `${path.basename(filePath)} - ${sourceName}`,
            type: 'sqlite',
            config: { filePath, query },
            createdAt: new Date().toISOString(),
            visualizations: [],
            analyses: [],
            transforms: []
        };
        const result = await pythonManager.send('preview_data', { data_source: newDataSource });
        newDataSource.previewData = result.payload;
        appState.dataSources[dataSourceId] = newDataSource;
        saveState();
        return newDataSource;
    } catch (error) {
        logError(error);
        throw error;
    }
});

async function handlePythonRequest(command, payload, stateUpdateLogic) {
    try {
        const result = await pythonManager.send(command, payload);

        // Differentiate between a successful call and a handled error from Python
        if (result.success) {
            if (stateUpdateLogic) {
                return stateUpdateLogic(result.payload);
            }
            return result.payload;
        } else {
            // This is a handled error from Python (e.g., code execution failed).
            // We pass it to the renderer as a "successful" response containing the error.
            return { __pyError: true, ...result.error };
        }
    } catch (error) {
        // This catches system-level errors (e.g., Python process crashed).
        logError(error);
        throw error; // Re-throw to reject the promise for the renderer.
    }
}

function getDataSourceConfig(dataSource) {
    if (dataSource.type === 'derived') {
        return {
            ...dataSource,
            all_data_sources: appState.dataSources
        };
    }
    return dataSource;
}

ipcMain.handle('set-active-model', async (event, modelId) => {
    appState.settings.activeModelId = modelId;
    saveState();
    const activeModel = appState.settings.models.find(m => m.id === appState.settings.activeModelId);
    if (activeModel) {
        await pythonManager.send('initialize_model_client', {
            model_provider: activeModel.provider,
            model_name: activeModel.modelName,
            api_key: activeModel.apiKey,
            base_url: activeModel.baseUrl
        });
    }
    return { success: true };
});

ipcMain.handle('generate-plot', (event, dataSourceId, command, transformId = null) => {
    const dataSource = getDataSourceConfig(appState.dataSources[dataSourceId]);
    const visualizationId = crypto.randomUUID();
    return handlePythonRequest('generate_plot', { data_source: dataSource, command, visualization_id: visualizationId, transform_id: transformId }, (result) => {
        if (!dataSource.visualizations) dataSource.visualizations = [];
        const newVis = { id: visualizationId, command, transformId, ...result };
        dataSource.visualizations.unshift(newVis);
        saveState();
        return newVis;
    }).then(result => {
        if (result.__pyError) {
            if (!dataSource.visualizations) dataSource.visualizations = [];
            const newVis = { id: visualizationId, command, transformId, ...result };
            dataSource.visualizations.unshift(newVis);
            saveState();
            return newVis;
        }
        return result;
    });
});

ipcMain.handle('modify-plot', (event, dataSourceId, visualizationId, existingCode, instruction) => {
    const dataSource = getDataSourceConfig(appState.dataSources[dataSourceId]);
    const originalVis = dataSource.visualizations.find((v, index) => v.id === visualizationId || index === visualizationId);
    const transformId = originalVis ? originalVis.transformId : null;
    return handlePythonRequest('modify_plot', { data_source: dataSource, visualization_id: visualizationId, existing_code: existingCode, instruction }, (result) => {
        const visIndex = dataSource.visualizations.findIndex((v, index) => v.id === visualizationId || index === visualizationId);
        if (visIndex > -1) {
            const originalVis = dataSource.visualizations[visIndex];
            const modifiedVis = { id: originalVis.id, command: `${originalVis.command} (modified: ${instruction})`, transformId: transformId, ...result };
            dataSource.visualizations[visIndex] = modifiedVis;
            saveState();
            return modifiedVis;
        }
    });
});

ipcMain.handle('run-modified-code', (event, dataSourceId, visualizationId, modifiedCode) => {
    // console.log(`[DEBUG] ipcMain: run-modified-code called with visualizationId: ${visualizationId}`);
    const dataSource = getDataSourceConfig(appState.dataSources[dataSourceId]);
    const originalVis = dataSource.visualizations.find((v, index) => v.id === visualizationId || index === visualizationId);
    const transformId = originalVis ? originalVis.transformId : null;
    return handlePythonRequest('run_code', { data_source: dataSource, visualization_id: visualizationId, code_to_run: modifiedCode, transform_id: transformId }, (result) => {
       // console.log(`[DEBUG] In stateUpdateLogic for run-modified-code. Searching for visualizationId: ${visualizationId}`);
        const visIndex = dataSource.visualizations.findIndex((v, index) => v.id === visualizationId || index === visualizationId);
        if (visIndex > -1) {
            const originalVis = dataSource.visualizations[visIndex];
            const updatedVis = { id: originalVis.id, command: originalVis.command, transformId: transformId, generatedCode: modifiedCode, ...result };
            dataSource.visualizations[visIndex] = updatedVis;
            saveState();
            // console.log('[DEBUG] Returning updatedVis:', updatedVis);
            return updatedVis;
        }
        // console.log('[DEBUG] Visualization not found. Returning undefined.');
    });
});

ipcMain.handle('analyze', (event, dataSourceId, command, transformId = null) => {
    const dataSource = getDataSourceConfig(appState.dataSources[dataSourceId]);
    const analysisId = crypto.randomUUID(); // Generate ID upfront
    return handlePythonRequest('analyze', { data_source: dataSource, command, transform_id: transformId }, (result) => {
        // This is the success path
        if (!dataSource.analyses) dataSource.analyses = [];
        const newAnalysis = { id: analysisId, command, transformId, ...result };
        dataSource.analyses.unshift(newAnalysis);
        saveState();
        return newAnalysis;
    }).then(result => {
        // This block catches both success and __pyError objects
        if (result.__pyError) {
            // If it's a python error, add the command and id before sending to renderer
            if (!dataSource.analyses) dataSource.analyses = [];
            const newAnalysis = { id: analysisId, command, transformId, ...result };
            dataSource.analyses.unshift(newAnalysis);
            saveState();
            return newAnalysis;
        }
        return result;
    });
});

ipcMain.handle('modify-analysis', (event, dataSourceId, analysisId, existingCode, instruction) => {
    const dataSource = getDataSourceConfig(appState.dataSources[dataSourceId]);
    const analysis = dataSource.analyses.find(a => a.id === analysisId);
    const transformId = analysis ? analysis.transformId : null;
    return handlePythonRequest('modify_analysis', { data_source: dataSource, existing_code: existingCode, instruction }, (result) => {
        const analysisIndex = dataSource.analyses.findIndex(a => a.id === analysisId);
        if (analysisIndex > -1) {
            const originalAnalysis = dataSource.analyses[analysisIndex];
            const modifiedAnalysis = { id: originalAnalysis.id, command: `${originalAnalysis.command} (modified: ${instruction})`, transformId: transformId, ...result };
            dataSource.analyses[analysisIndex] = modifiedAnalysis;
            saveState();
            return modifiedAnalysis;
        }
    });
});

ipcMain.handle('run-modified-analysis-code', (event, dataSourceId, analysisId, modifiedCode) => {
    const dataSource = getDataSourceConfig(appState.dataSources[dataSourceId]);
    const analysis = dataSource.analyses.find(a => a.id === analysisId);
    const transformId = analysis ? analysis.transformId : null;
    return handlePythonRequest('run_analysis_code', { data_source: dataSource, code_to_run: modifiedCode, transform_id: transformId }, (result) => {
        const analysisIndex = dataSource.analyses.findIndex(a => a.id === analysisId);
        if (analysisIndex > -1) {
            const originalAnalysis = dataSource.analyses[analysisIndex];
            const updatedAnalysis = { id: originalAnalysis.id, command: originalAnalysis.command, transformId: transformId, generatedCode: modifiedCode, ...result };
            dataSource.analyses[analysisIndex] = updatedAnalysis;
            saveState();
            return updatedAnalysis;
        }
    });
});

ipcMain.handle('transform', (event, dataSourceId, command) => {
    const dataSource = getDataSourceConfig(appState.dataSources[dataSourceId]);
    const transformId = crypto.randomUUID();
    return handlePythonRequest('transform', { data_source: dataSource, command, transform_id: transformId }, (result) => {
        if (!dataSource.transforms) dataSource.transforms = [];
        const newTransform = { id: transformId, command, ...result };
        dataSource.transforms.unshift(newTransform);
        saveState();
        return newTransform;
    }).then(result => {
        if (result.__pyError) {
            if (!dataSource.transforms) dataSource.transforms = [];
            const newTransform = { id: transformId, command, ...result };
            dataSource.transforms.unshift(newTransform);
            saveState();
            return newTransform;
        }
        return result;
    });
});

ipcMain.handle('modify-transform', (event, dataSourceId, transformId, existingCode, instruction) => {
    const dataSource = getDataSourceConfig(appState.dataSources[dataSourceId]);
    return handlePythonRequest('modify_transform', { data_source: dataSource, existing_code: existingCode, instruction, transform_id: transformId }, (result) => {
        const transformIndex = dataSource.transforms.findIndex(t => t.id === transformId);
        if (transformIndex > -1) {
            const originalTransform = dataSource.transforms[transformIndex];
            const modifiedTransform = { id: originalTransform.id, command: `${originalTransform.command} (modified: ${instruction})`, ...result };
            dataSource.transforms[transformIndex] = modifiedTransform;
            saveState();
            return modifiedTransform;
        }
    });
});

ipcMain.handle('run-modified-transform-code', (event, dataSourceId, transformId, modifiedCode) => {
    const dataSource = getDataSourceConfig(appState.dataSources[dataSourceId]);
    return handlePythonRequest('run_transform_code', { data_source: dataSource, code_to_run: modifiedCode, transform_id: transformId }, (result) => {
        const transformIndex = dataSource.transforms.findIndex(t => t.id === transformId);
        if (transformIndex > -1) {
            const originalTransform = dataSource.transforms[transformIndex];
            const updatedTransform = { id: originalTransform.id, command: originalTransform.command, generatedCode: modifiedCode, ...result };
            dataSource.transforms[transformIndex] = updatedTransform;
            saveState();
            return updatedTransform;
        }
    });
});

ipcMain.handle('new-transform', (event, dataSourceId, parentTransformId, instruction) => {
    const dataSource = getDataSourceConfig(appState.dataSources[dataSourceId]);
    const newTransformId = crypto.randomUUID();
    return handlePythonRequest('new_transform', { 
        data_source: dataSource, 
        parent_transform_id: parentTransformId, 
        instruction, 
        new_transform_id: newTransformId 
    }, (result) => {
        if (!dataSource.transforms) dataSource.transforms = [];
        // console.log(`DEBUG: ${result}`);
        const newTransform = { id: newTransformId, command: instruction, basedOn: parentTransformId, ...result };
        dataSource.transforms.unshift(newTransform);
        saveState();
        return newTransform;
    }).then(result => {
        if (result.__pyError) {
            if (!dataSource.transforms) dataSource.transforms = [];
            // console.log(`DEBUG: ${result}`);
            const newTransform = { id: newTransformId, command: instruction, basedOn: parentTransformId, ...result };
            dataSource.transforms.unshift(newTransform);
            saveState();
            return newTransform;
        }
        return result;
    });
});

ipcMain.handle('load-more-data', (event, { dataSourceId, transformId, offset, limit }) => {
  const dataSource = getDataSourceConfig(appState.dataSources[dataSourceId]);
    return handlePythonRequest('load_more_data', { 
        data_source: dataSource, 
        transform_id: transformId, 
        offset, 
        limit 
    });
});

ipcMain.handle('export-transform-data', async (event, { dataSourceId, transformId }) => {
    const dataSource = appState.dataSources[dataSourceId];
    const transform = dataSource?.transforms.find(t => t.id === transformId);

    let defaultName = `transform-${transformId}.csv`;
    if (transform) {
        // Sanitize the name to be a valid filename
        const saneName = (transform.name || transform.command)
            .replace(/[^a-z0-9_.-]/gi, '_')
            .substring(0, 50);
        defaultName = `${saneName}.csv`;
    }

    const { canceled, filePath } = await dialog.showSaveDialog({
        title: 'Export Transform Data',
        defaultPath: defaultName,
        filters: [{ name: 'CSV Files', extensions: ['csv'] }]
    });

    if (canceled || !filePath) {
        return { success: false, reason: 'Save dialog canceled' };
    }

    try {
        const dataSource = getDataSourceConfig(appState.dataSources[dataSourceId]);
        const csvData = await pythonManager.send('export_transform_data', {
            data_source: dataSource,
            transform_id: transformId
        });

        fs.writeFileSync(filePath, csvData.payload);
        return { success: true };
    } catch (error) {
        logError(error);
        dialog.showErrorBox('Export Error', 'Failed to export data.');
        return { success: false, reason: error.message };
    }
});

ipcMain.handle('create-derived-data-source', async (event, { selectedSources, newName, instruction }) => {
    try {
        const dataSourceId = crypto.randomUUID();
        
        // We need to pass the full data source objects to the backend
        const sourcesForBackend = selectedSources.map(sourceString => {
            const [type, dsId, trId] = sourceString.split(':');
            const dataSource = getDataSourceConfig(appState.dataSources[dsId]);
            if (type === 'ds') {
                return { ...dataSource, latest_transform_id: null };
            } else if (type === 'tr') {
                return { ...dataSource, latest_transform_id: trId };
            }
        });

        const result = await pythonManager.send('create_derived_data_source', {
            sources: sourcesForBackend,
            instruction,
            new_data_source_id: dataSourceId
        });


        const newDataSource = {
            id: dataSourceId,
            name: newName,
            type: 'derived',
            config: {
                sources: selectedSources,
                instruction: instruction,
                generatedCode: result.payload.generatedCode
            },
            createdAt: new Date().toISOString(),
            previewData: result.payload.previewData,
            visualizations: [],
            analyses: [],
            transforms: []
        };

        appState.dataSources[dataSourceId] = newDataSource;
        saveState();
        return newDataSource;
    } catch (error) {
        logError(error);
        throw error;
    }
});

ipcMain.handle('delete-transform', async (event, dataSourceId, transformId) => {
    if (appState.dataSources[dataSourceId]?.transforms) {
        const transforms = appState.dataSources[dataSourceId].transforms;
        const transformIndex = transforms.findIndex(t => t.id === transformId);
        if (transformIndex > -1) {
            transforms.splice(transformIndex, 1);
            saveState();
        }
    }
    return { success: true };
});

ipcMain.handle('update-item-name', async (event, { dataSourceId, itemId, itemType, name }) => {
    try {
        const dataSource = getDataSourceConfig(appState.dataSources[dataSourceId]);
        if (!dataSource) {
            throw new Error(`Data source with id ${dataSourceId} not found`);
        }

        const itemCollection = dataSource[itemType];
        if (!itemCollection) {
            throw new Error(`Invalid item type: ${itemType}`);
        }

        const item = itemCollection.find(i => i.id === itemId);
        if (!item) {
            throw new Error(`Item with id ${itemId} not found in ${itemType}`);
        }

        item.name = name;
        saveState();
        return { success: true };
    } catch (error) {
        logError(error);
        return { success: false, error: error.message };
    }
});


ipcMain.handle('show-error-dialog', (event, { title, content }) => {
    const window = BrowserWindow.getFocusedWindow();
    dialog.showErrorBox(title, content, window);
});

ipcMain.on('show-plot-context-menu', (event, imageData) => {
    const image = nativeImage.createFromDataURL(imageData);
    const menuTemplate = [
        {
            label: 'Copy Image',
            click: () => {
                clipboard.writeImage(image);
            }
        },
        {
            label: 'Save Image As...',
            click: async () => {
                const { canceled, filePath } = await dialog.showSaveDialog({
                    title: 'Save Plot',
                    defaultPath: 'plot.png',
                    filters: [{ name: 'Images', extensions: ['png'] }]
                });
                if (!canceled && filePath) {
                    const base64Data = imageData.replace(/^data:image\/png;base64,/, '');
                    try {
                        fs.writeFileSync(filePath, base64Data, 'base64');
                    } catch (e) {
                        logError(`Failed to save image: ${e}`);
                        // Optionally, inform the user
                        dialog.showErrorBox('Save Error', 'Failed to save the image.');
                    }
                }
            }
        }
    ];
    const menu = Menu.buildFromTemplate(menuTemplate);
    menu.popup({ window: BrowserWindow.fromWebContents(event.sender) });
});

ipcMain.handle('delete-visualization', async (event, dataSourceId, visualizationId) => {
    if (appState.dataSources[dataSourceId]?.visualizations) {
        const visualizations = appState.dataSources[dataSourceId].visualizations;
        const visIndex = visualizations.findIndex((v, index) => v.id === visualizationId || index === visualizationId);
        if (visIndex > -1) {
            visualizations.splice(visIndex, 1);
            saveState();
        }
    }
    return { success: true };
});

ipcMain.handle('delete-analysis', async (event, dataSourceId, analysisId) => {
    if (appState.dataSources[dataSourceId]?.analyses) {
        const analyses = appState.dataSources[dataSourceId].analyses;
        const analysisIndex = analyses.findIndex(a => a.id === analysisId);
        if (analysisIndex > -1) {
            analyses.splice(analysisIndex, 1);
            saveState();
        }
    }
    return { success: true };
});

ipcMain.handle('delete-data-source', async (event, dataSourceId, activeDataSourceId) => {
    if (appState.dataSources[dataSourceId]) {
        const dataSourceIds = Object.keys(appState.dataSources);
        const deletedIndex = dataSourceIds.indexOf(dataSourceId);
        
        delete appState.dataSources[dataSourceId];
        saveState();

        const remainingIds = Object.keys(appState.dataSources);
        let nextTabId = null;
        if (remainingIds.length > 0) {
            if (activeDataSourceId === dataSourceId) {
                const newIndex = Math.max(0, deletedIndex - 1);
                nextTabId = remainingIds[newIndex];
            } else {
                nextTabId = activeDataSourceId;
            }
        }
        return { success: true, nextTabId };
    }
    return { success: false, error: 'Data source not found.' };
});


app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('will-quit', () => {
    if (pythonManager && pythonManager.pythonProcess) {
        pythonManager.pythonProcess.kill();
    }
});