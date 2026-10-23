pipeline {
    agent any

    triggers {
        cron('0 2,9,18 * * *')  // 每天凌晨2点、早上9点、下午6点执行
    }

    environment {
        VENV_DIR = '.venv'
        PYTHON_HOME = 'C:\\Users\\shengwang.ma\\AppData\\Local\\Programs\\Python\\Python314'
    }

    parameters {
        choice(name: 'BROWSER', choices: ['chromium', 'firefox', 'webkit'], description: '选择浏览器')
        booleanParam(name: 'HEADLESS', defaultValue: true, description: '是否无头模式运行')
        string(name: 'TEST_MARKER', defaultValue: '', description: 'pytest marker 过滤，如 smoke、login')
        choice(name: 'TEST_TYPE', choices: ['all', 'ui', 'api'], description: '测试类型：all=全部, ui=UI自动化, api=接口自动化')
        choice(name: 'ENV', choices: ['qa', 'qa_staging'], description: '选择运行环境')
        string(name: 'QA_URL', defaultValue: '', description: '被测平台地址，留空则取 config/env_config.yaml')
        string(name: 'QA_USERNAME', defaultValue: '', description: '登录账号，留空则取配置文件')
        password(name: 'QA_PASSWORD', defaultValue: '', description: '登录口令（建议配 Jenkins 凭证，勿入库）')
    }

    stages {
        stage('安装依赖') {
            steps {
                bat """
                    "%PYTHON_HOME%\\python.exe" -m venv %VENV_DIR%
                    call %VENV_DIR%\\Scripts\\activate.bat
                    pip install -r requirements.txt
                    if "${params.TEST_TYPE}" NEQ "api" (
                        playwright install ${params.BROWSER}
                    )
                """
            }
        }

        stage('执行测试') {
                steps {
                    bat """
                        call %VENV_DIR%\\Scripts\\activate.bat

                        rd /s /q reports\\allure-results 2>nul
                        rd /s /q allure-results 2>nul
                        mkdir reports\\allure-results 2>nul

                        set BROWSER=${params.BROWSER}
                        set HEADLESS=${params.HEADLESS}
                        ${params.QA_URL ? 'set QA_URL=' + params.QA_URL : ''}
                        ${params.QA_USERNAME ? 'set QA_USERNAME=' + params.QA_USERNAME : ''}
                        ${params.QA_PASSWORD ? 'set QA_PASSWORD=' + params.QA_PASSWORD : ''}

                    pytest --env=${params.ENV} --alluredir=reports/allure-results --clean-alluredir ${params.TEST_TYPE != 'all' ? '-m ' + params.TEST_TYPE : ''} ${params.TEST_MARKER ? '-m ' + params.TEST_MARKER : ''}
                    exit /b 0
                """
            }
        }
    }

    post {
        always {
            script {
                try {
                    echo "开始准备飞书通知..."
                    def allureUrl = "${env.ALLURE_BASE_URL ?: 'http://localhost:8080/job/'}${env.JOB_NAME}/${env.BUILD_NUMBER}/allure"
                    def status = currentBuild.result ?: 'SUCCESS'

                    // 读取用例详情
                    def testDetails = ""
                    def passed = 0
                    def failed = 0
                    def total = 0
                    def passRate = '0%'

                    try {
                        // 使用 dir 命令列出文件
                        def fileList = bat(script: "dir /b reports\\allure-results\\*-result.json 2>nul", returnStdout: true).trim()

                        echo "找到的测试结果文件: ${fileList}"

                        if (fileList) {
                            def uiPassedList = []
                            def uiFailedList = []
                            def apiPassedList = []
                            def apiFailedList = []

                            fileList.split('\n').each { fileName ->
                                fileName = fileName.trim()
                                if (fileName && fileName.endsWith('-result.json')) {
                                    def filePath = "reports/allure-results/${fileName}"

                                    if (fileExists(filePath)) {
                                        def content = readFile(file: filePath, encoding: 'UTF-8')

                                        // 提取 fullName
                                        def fullNameMatcher = content =~ /"fullName"\s*:\s*"([^"]+)"/
                                        // 提取状态
                                        def statusMatcher = content =~ /"status"\s*:\s*"(passed|failed|broken)"/

                                        if (fullNameMatcher.find() && statusMatcher.find()) {
                                            def fullName = fullNameMatcher.group(1)
                                            def testStatus = statusMatcher.group(1)

                                            // 取 # 前面的模块路径
                                            def modulePath = fullName.contains('#') ? fullName.split('#')[0] : fullName
                                            // 取最后一段作为模块名
                                            def pathParts = modulePath.split('\\.')
                                            def moduleName2 = pathParts[pathParts.length - 1]

                                            // 过滤非用例文件（平台用例统一 test_ 开头）
                                            if (!moduleName2.startsWith('test_')) {
                                                return
                                            }

                                            // 判断是接口自动化还是 UI 自动化
                                            def isApi = moduleName2.startsWith('test_api')

                                            // 去掉 test_ 前缀得到可读用例名
                                            def testName = moduleName2.startsWith('test_') ? moduleName2.substring(5) : moduleName2

                                            if (testStatus == 'passed') {
                                                if (isApi) {
                                                    apiPassedList.add(testName)
                                                } else {
                                                    uiPassedList.add(testName)
                                                }
                                            } else {
                                                if (isApi) {
                                                    apiFailedList.add(testName)
                                                } else {
                                                    uiFailedList.add(testName)
                                                }
                                            }

                                            echo "解析成功: ${testName} - ${testStatus} - ${isApi ? 'API' : 'UI'}"
                                        }
                                    }
                                }
                            }

                            // 去重：同一用例重试后通过算通过
                            def uniqueUiPassed = uiPassedList.unique()
                            def uniqueUiFailed = uiFailedList.unique()
                            uniqueUiFailed.removeAll(uniqueUiPassed)

                            def uniqueApiPassed = apiPassedList.unique()
                            def uniqueApiFailed = apiFailedList.unique()
                            uniqueApiFailed.removeAll(uniqueApiPassed)

                            def uiPassed = uniqueUiPassed.size()
                            def uiFailed = uniqueUiFailed.size()
                            def apiPassed = uniqueApiPassed.size()
                            def apiFailed = uniqueApiFailed.size()

                            passed = uiPassed + apiPassed
                            failed = uiFailed + apiFailed
                            total = passed + failed
                            if (total > 0) {
                                passRate = String.format("%.1f%%", (passed * 100.0 / total))
                            }

                            // 计算 UI 和 API 各自的通过率
                            def uiTotal = uiPassed + uiFailed
                            def apiTotal = apiPassed + apiFailed
                            def uiPassRate = uiTotal > 0 ? String.format("%.1f%%", (uiPassed * 100.0 / uiTotal)) : "N/A"
                            def apiPassRate = apiTotal > 0 ? String.format("%.1f%%", (apiPassed * 100.0 / apiTotal)) : "N/A"

                            testDetails = ""

                            // UI 测试结果
                            if (uiPassed > 0 || uiFailed > 0) {
                                testDetails += "\\n\\n**UI自动化** (通过率: ${uiPassRate})\\n"
                                if (uniqueUiPassed) {
                                    testDetails += "✅ 通过: ${uniqueUiPassed.join(', ')}\\n"
                                }
                                if (uniqueUiFailed) {
                                    testDetails += "❌ 失败: ${uniqueUiFailed.join(', ')}\\n"
                                }
                            }

                            // API 测试结果
                            if (apiPassed > 0 || apiFailed > 0) {
                                testDetails += "\\n**接口自动化** (通过率: ${apiPassRate})\\n"
                                if (uniqueApiPassed) {
                                    testDetails += "✅ 通过: ${uniqueApiPassed.join(', ')}\\n"
                                }
                                if (uniqueApiFailed) {
                                    testDetails += "❌ 失败: ${uniqueApiFailed.join(', ')}\\n"
                                }
                            }

                            echo "用例详情构建完成: ${testDetails}"
                        } else {
                            echo "警告: 没有找到测试结果文件"
                        }
                    } catch (Exception e) {
                        echo "解析用例详情失败: ${e.message}"
                    }

                    def color = status == 'SUCCESS' ? 'green' : 'red'

                    echo "准备发送飞书通知..."
                    echo "通过率: ${passRate}, 通过=${passed}, 失败=${failed}, 总数=${total}"

                    def payload = """{
                        "msg_type": "interactive",
                        "card": {
                            "header": {
                                "title": {"tag": "plain_text", "content": "自动化测试报告 #${env.BUILD_NUMBER}"},
                                "template": "${color}"
                            },
                            "elements": [
                                {
                                    "tag": "div",
                                    "text": {
                                        "tag": "lark_md",
                                        "content": "**项目:** ${env.JOB_NAME}\\n**环境:** ${params.ENV}\\n**测试类型:** ${params.TEST_TYPE}\\n**浏览器:** ${params.BROWSER}\\n**整体通过率:** ${passRate} (${passed}/${total})${testDetails}"
                                    }
                                },
                                {
                                    "tag": "action",
                                    "actions": [
                                        {
                                            "tag": "button",
                                            "text": {"tag": "plain_text", "content": "查看自动化测试报告"},
                                            "url": "${allureUrl}",
                                            "type": "primary"
                                        }
                                    ]
                                }
                            ]
                        }
                    }"""

                    echo "发送飞书通知..."
                    // Webhook 地址从环境变量读取，避免明文入库
                    def webhookUrls = (env.FEISHU_WEBHOOK_URLS ?: '').split(',')
                        .collect { it.trim() }.findAll { !it.isEmpty() }

                    if (webhookUrls.isEmpty()) {
                        echo "未配置 FEISHU_WEBHOOK_URLS，跳过飞书通知"
                        return
                    }

                    webhookUrls.each { url ->
                        try {
                            httpRequest httpMode: 'POST',
                                url: url,
                                contentType: 'APPLICATION_JSON',
                                requestBody: payload
                            echo "通知发送成功: ${url}"
                        } catch (Exception ex) {
                            echo "通知发送失败: ${url}, 原因: ${ex.message}"
                        }
                    }
                    echo "飞书通知发送完成"
                } catch (Exception e) {
                    echo "飞书通知发送失败: ${e.message}"
                    e.printStackTrace()
                }
            }

            allure includeProperties: false,
                   jdk: '',
                   results: [[path: 'reports/allure-results']]

            archiveArtifacts artifacts: 'failed_screenshots/**/*.png', allowEmptyArchive: true
        }
    }
}
