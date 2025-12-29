#!/usr/bin/env node

/**
 * ts-morph Bridge for Python
 * 
 * This script provides AST-based parsing for JavaScript/TypeScript files
 * using the ts-morph library (TypeScript compiler wrapper).
 * 
 * Usage: node tsmorph_bridge.js <file_path>
 * Output: JSON string to stdout
 * 
 * Install dependencies:
 *   npm install ts-morph
 */

const fs = require('fs');
const path = require('path');

// Check if ts-morph is available
let Project;
try {
    const tsm = require('ts-morph');
    Project = tsm.Project;
} catch (error) {
    console.error(JSON.stringify({
        error: 'ts-morph not installed. Run: npm install ts-morph'
    }));
    process.exit(1);
}

/**
 * Parse a JavaScript/TypeScript file and extract structure
 */
function parseFile(filePath) {
    try {
        // Create a new Project
        const project = new Project({
            skipAddingFilesFromTsConfig: true,
            compilerOptions: {
                allowJs: true,
                checkJs: false,
                noLib: true,
                target: 99, // ESNext
                module: 99, // ESNext
            }
        });

        // Add the file to the project
        const sourceFile = project.addSourceFileAtPath(filePath);
        
        const result = {
            file_type: filePath.endsWith('.ts') || filePath.endsWith('.tsx') ? 'typescript' : 'javascript',
            imports: [],
            exports: [],
            classes: [],
            functions: [],
            methods: []
        };

        // Extract imports
        sourceFile.getImportDeclarations().forEach(imp => {
            const moduleSpecifier = imp.getModuleSpecifierValue();
            const namedImports = imp.getNamedImports().map(ni => ni.getName());
            const defaultImport = imp.getDefaultImport()?.getText();
            const namespaceImport = imp.getNamespaceImport()?.getText();
            
            result.imports.push({
                type: 'es6',
                module: moduleSpecifier,
                named: namedImports,
                default: defaultImport,
                namespace: namespaceImport,
                line: imp.getStartLineNumber()
            });
        });

        // Extract exports
        sourceFile.getExportDeclarations().forEach(exp => {
            const moduleSpecifier = exp.getModuleSpecifierValue();
            const namedExports = exp.getNamedExports().map(ne => ne.getName());
            
            result.exports.push({
                type: 'es6',
                module: moduleSpecifier,
                named: namedExports,
                line: exp.getStartLineNumber()
            });
        });

        // Extract classes
        sourceFile.getClasses().forEach(cls => {
            const classInfo = {
                name: cls.getName() || '<anonymous>',
                line: cls.getStartLineNumber(),
                is_exported: cls.isExported(),
                is_default: cls.isDefaultExport(),
                is_abstract: cls.isAbstract(),
                extends: cls.getExtends()?.getText(),
                implements: cls.getImplements().map(i => i.getText()),
                methods: []
            };

            // Extract methods from the class
            cls.getMethods().forEach(method => {
                const methodInfo = {
                    name: method.getName(),
                    line: method.getStartLineNumber(),
                    is_async: method.isAsync(),
                    is_static: method.isStatic(),
                    is_abstract: method.isAbstract(),
                    parameters: method.getParameters().map(p => ({
                        name: p.getName(),
                        type: p.getType().getText(),
                        is_optional: p.isOptional(),
                        is_rest: p.isRestParameter()
                    })),
                    return_type: method.getReturnType().getText()
                };
                classInfo.methods.push(methodInfo);
                
                // Also add to global methods list with class association
                result.methods.push({
                    ...methodInfo,
                    class_name: classInfo.name
                });
            });

            // Extract constructor
            const constructor = cls.getConstructors()[0];
            if (constructor) {
                const constructorInfo = {
                    name: 'constructor',
                    line: constructor.getStartLineNumber(),
                    is_async: false,
                    is_static: false,
                    parameters: constructor.getParameters().map(p => ({
                        name: p.getName(),
                        type: p.getType().getText(),
                        is_optional: p.isOptional()
                    }))
                };
                classInfo.methods.push(constructorInfo);
                
                result.methods.push({
                    ...constructorInfo,
                    class_name: classInfo.name
                });
            }

            result.classes.push(classInfo);
        });

        // Extract top-level functions
        sourceFile.getFunctions().forEach(func => {
            const functionInfo = {
                name: func.getName() || '<anonymous>',
                line: func.getStartLineNumber(),
                is_async: func.isAsync(),
                is_exported: func.isExported(),
                is_default: func.isDefaultExport(),
                is_generator: func.isGenerator(),
                is_arrow: false,
                parameters: func.getParameters().map(p => ({
                    name: p.getName(),
                    type: p.getType().getText(),
                    is_optional: p.isOptional(),
                    is_rest: p.isRestParameter()
                })),
                return_type: func.getReturnType().getText(),
                class_name: null
            };
            result.functions.push(functionInfo);
        });

        // Extract arrow functions and function expressions assigned to variables
        sourceFile.getVariableDeclarations().forEach(varDecl => {
            const initializer = varDecl.getInitializer();
            if (!initializer) return;

            const isArrow = initializer.getKindName() === 'ArrowFunction';
            const isFuncExpr = initializer.getKindName() === 'FunctionExpression';

            if (isArrow || isFuncExpr) {
                const functionInfo = {
                    name: varDecl.getName(),
                    line: varDecl.getStartLineNumber(),
                    is_async: initializer.isAsync ? initializer.isAsync() : false,
                    is_exported: varDecl.getVariableStatement()?.isExported() || false,
                    is_default: varDecl.getVariableStatement()?.isDefaultExport() || false,
                    is_generator: initializer.isGenerator ? initializer.isGenerator() : false,
                    is_arrow: isArrow,
                    parameters: initializer.getParameters ? initializer.getParameters().map(p => ({
                        name: p.getName(),
                        type: p.getType ? p.getType().getText() : 'any',
                        is_optional: p.isOptional ? p.isOptional() : false,
                        is_rest: p.isRestParameter ? p.isRestParameter() : false
                    })) : [],
                    return_type: initializer.getReturnType ? initializer.getReturnType().getText() : 'any',
                    class_name: null
                };
                result.functions.push(functionInfo);
            }
        });

        // Output the result as JSON
        console.log(JSON.stringify(result, null, 2));
        process.exit(0);

    } catch (error) {
        console.error(JSON.stringify({
            error: error.message,
            stack: error.stack
        }));
        process.exit(1);
    }
}

// Main execution
if (process.argv.length < 3) {
    console.error(JSON.stringify({
        error: 'Usage: node tsmorph_bridge.js <file_path>'
    }));
    process.exit(1);
}

const filePath = process.argv[2];

// Check if file exists
if (!fs.existsSync(filePath)) {
    console.error(JSON.stringify({
        error: `File not found: ${filePath}`
    }));
    process.exit(1);
}

// Parse the file
parseFile(filePath);

