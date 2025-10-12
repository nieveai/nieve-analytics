module.exports = {
    testEnvironment: 'node',
    moduleNameMapper: {
        '^zeromq$': '<rootDir>/__mocks__/zeromq.js'
    },
    setupFilesAfterEnv: ['./test/setup.js']
};