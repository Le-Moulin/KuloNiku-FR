import Cocoa
import CryptoKit
import UniformTypeIdentifiers

private final class StatusActionButton: NSButton {
    override func resetCursorRects() {
        super.resetCursorRects()
        if !isHidden && isEnabled {
            addCursorRect(bounds, cursor: .pointingHand)
        }
    }
}

private struct InstallationStatus: Decodable {
    let state: String
    let translationState: String
    let backupAvailable: Bool
    let edition: String
    let availableBundleSHA256: String
    let installedPatcherVersion: String?
    let sourceRecognition: String?

    enum CodingKeys: String, CodingKey {
        case state
        case translationState = "translation_state"
        case backupAvailable = "backup_available"
        case edition
        case availableBundleSHA256 = "available_bundle_sha256"
        case installedPatcherVersion = "installed_patcher_version"
        case sourceRecognition = "source_recognition"
    }
}

private struct UpdateManifest: Decodable {
    let version: String
    let translationBundles: [String: String]
    let translationPackage: TranslationPackage?

    enum CodingKeys: String, CodingKey {
        case version
        case translationBundles = "translation_bundles"
        case translationPackage = "translation_package"
    }
}

private struct TranslationPackage: Decodable {
    let version: String
    let asset: String
    let sha256: String
    let minimumPatcherVersion: String
    let bundles: [String: String]

    enum CodingKeys: String, CodingKey {
        case version
        case asset
        case sha256
        case minimumPatcherVersion = "minimum_patcher_version"
        case bundles
    }
}

private func comparableVersion(_ rawValue: String) -> [Int] {
    let pattern = #"(\d+)\.(\d+)\.(\d+)(?:[-.]?(alpha|beta|rc|a|b)(?:[.-]?(\d+))?)?"#
    guard let expression = try? NSRegularExpression(pattern: pattern),
          let match = expression.firstMatch(
              in: rawValue.lowercased(),
              range: NSRange(rawValue.startIndex..., in: rawValue)
          )
    else { return [0, 0, 0, 3, 0] }

    func capture(_ index: Int) -> String? {
        let range = match.range(at: index)
        guard range.location != NSNotFound,
              let swiftRange = Range(range, in: rawValue.lowercased())
        else { return nil }
        return String(rawValue.lowercased()[swiftRange])
    }

    let major = Int(capture(1) ?? "0") ?? 0
    let minor = Int(capture(2) ?? "0") ?? 0
    let patch = Int(capture(3) ?? "0") ?? 0
    let stage: Int
    switch capture(4) {
    case "a", "alpha": stage = 0
    case "b", "beta": stage = 1
    case "rc": stage = 2
    default: stage = 3
    }
    let prereleaseNumber = Int(capture(5) ?? "0") ?? 0
    return [major, minor, patch, stage, prereleaseNumber]
}

private func isVersion(_ candidate: String, newerThan current: String) -> Bool {
    let candidateKey = comparableVersion(candidate)
    let currentKey = comparableVersion(current)
    for (candidatePart, currentPart) in zip(candidateKey, currentKey) {
        if candidatePart != currentPart {
            return candidatePart > currentPart
        }
    }
    return false
}

private func isPrereleaseVersion(_ version: String) -> Bool {
    comparableVersion(version)[3] < 3
}

private func newerTranslationPackage(
    in manifest: UpdateManifest?,
    edition: String,
    activeVersion: String,
    activeHash: String
) -> TranslationPackage? {
    guard let manifest,
          let package = manifest.translationPackage,
          isVersion(package.version, newerThan: activeVersion),
          let remoteHash = manifest.translationBundles[edition],
          package.bundles[edition] == remoteHash,
          remoteHash != activeHash
    else { return nil }
    return package
}

private func runUpdatePolicySelfTest() -> Int32 {
    func manifest(_ version: String, hash: String = "remote") -> UpdateManifest {
        UpdateManifest(version: version, translationBundles: ["full": hash],
            translationPackage: TranslationPackage(version: version, asset: "translations.zip",
                sha256: "archive", minimumPatcherVersion: "1.4.0", bundles: ["full": hash]))
    }
    let cases: [(UpdateManifest?, String, String, Bool)] = [
        (manifest("1.3.1"), "1.4.0", "local", false),
        (manifest("1.4.0"), "1.4.0", "local", false),
        (manifest("1.4.1"), "1.4.0", "local", true),
        (manifest("1.4.1", hash: "local"), "1.4.0", "local", false),
        (manifest("1.4.1"), "1.5.0", "local", false),
        (manifest("1.5.0"), "1.5.0", "local", false),
        (manifest("1.4.1-beta.1"), "1.4.1", "local", false),
        (nil, "1.4.0", "local", false),
    ]
    for (index, test) in cases.enumerated() {
        let accepted = newerTranslationPackage(in: test.0, edition: "full",
            activeVersion: test.1, activeHash: test.2) != nil
        guard accepted == test.3 else {
            fputs("Échec du scénario de mise à jour \(index + 1).\n", stderr)
            return 1
        }
    }
    print("8 scénarios de mise à jour vérifiés.")
    return 0
}

private var bundledPatcherExecutable: String {
    #if arch(arm64)
    return "KuloNiku-FR-arm64"
    #elseif arch(x86_64)
    return "KuloNiku-FR-x86_64"
    #else
    #error("Architecture macOS non prise en charge")
    #endif
}

private func runLauncherSelfTest() -> Int32 {
    let launcher = URL(fileURLWithPath: CommandLine.arguments[0]).standardizedFileURL
    let resources = launcher
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .appendingPathComponent("Resources", isDirectory: true)
    let patcher = resources.appendingPathComponent(bundledPatcherExecutable)
    guard FileManager.default.isExecutableFile(atPath: patcher.path) else {
        fputs("Moteur intégré introuvable : \(patcher.path)\n", stderr)
        return 1
    }
    let translationResources = resources.appendingPathComponent("translations", isDirectory: true)
    let requiredResources = [
        "fr.csv",
        "review-overrides.csv",
        "TERMINOLOGY.md",
        "AGENT_BRIEF.md",
    ]
    for name in requiredResources {
        let path = translationResources.appendingPathComponent(name)
        guard FileManager.default.isReadableFile(atPath: path.path) else {
            fputs("Ressource intégrée introuvable : \(path.path)\n", stderr)
            return 1
        }
    }

    let task = Process()
    let pipe = Pipe()
    task.executableURL = patcher
    task.arguments = ["--version"]
    task.standardOutput = pipe
    task.standardError = pipe
    task.currentDirectoryURL = resources
    do {
        try task.run()
        task.waitUntilExit()
        let output = pipe.fileHandleForReading.readDataToEndOfFile()
        FileHandle.standardOutput.write(output)
        return task.terminationStatus
    } catch {
        fputs("Impossible de lancer le moteur intégré : \(error.localizedDescription)\n", stderr)
        return 1
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private let repositoryURL = URL(string: "https://github.com/Le-Moulin/KuloNiku-FR")!
    private var window: NSWindow!
    private var gamePathField: NSTextField!
    private var logView: NSTextView!
    private var analyzeButton: NSButton!
    private var installButton: NSButton!
    private var restoreButton: NSButton!
    private var chooseButton: NSButton!
    private var releaseButton: NSButton!
    private var appUpdateRow: NSStackView!
    private var appUpdateMessage: NSTextField!
    private var advancedButton: NSButton!
    private var advancedStack: NSStackView!
    private var detailsButton: NSButton!
    private var reviewButton: NSButton!
    private var testReviewButton: NSButton!
    private var logScroll: NSScrollView!
    private var statusIcon: NSImageView!
    private var statusActionButton: StatusActionButton!
    private var statusTitle: NSTextField!
    private var statusMessage: NSTextField!
    private var progressIndicator: NSProgressIndicator!
    private var selectedGameURL: URL?
    private var latestReleaseURL: URL?
    private var downloadedTranslationsURL: URL?
    private var downloadedTranslationsVersion: String?
    private var translationDownloadInProgress = false
    private var installerUpdateRequired = false
    private var simulationSucceeded = false
    private var restoreAvailable = false
    private var advancedVisible = false
    private var detailsVisible = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApplication.shared.setActivationPolicy(.regular)
        configureApplicationMenu()
        buildWindow()
        checkLatestRelease()
        selectDefaultInstallationIfAvailable()
        window.makeKeyAndOrderFront(nil)
        window.orderFrontRegardless()
        NSApplication.shared.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    private func configureApplicationMenu() {
        let mainMenu = NSMenu()
        let appMenuItem = NSMenuItem()
        mainMenu.addItem(appMenuItem)

        let appMenu = NSMenu()
        appMenu.addItem(
            withTitle: "À propos de KuloNiku FR",
            action: #selector(showAbout),
            keyEquivalent: ""
        )
        appMenu.addItem(.separator())
        appMenu.addItem(
            withTitle: "Quitter KuloNiku FR",
            action: #selector(NSApplication.terminate(_:)),
            keyEquivalent: "q"
        )
        appMenuItem.submenu = appMenu
        NSApplication.shared.mainMenu = mainMenu
    }

    private func buildWindow() {
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 760, height: 440),
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = "KuloNiku FR"
        window.center()
        window.isReleasedWhenClosed = false

        let content = NSView()
        window.contentView = content

        let title = NSTextField(labelWithString: "KuloNiku en français")
        title.font = .systemFont(ofSize: 26, weight: .bold)

        statusIcon = NSImageView()
        statusIcon.imageScaling = .scaleProportionallyUpOrDown
        statusIcon.translatesAutoresizingMaskIntoConstraints = false

        progressIndicator = NSProgressIndicator()
        progressIndicator.style = .spinning
        progressIndicator.controlSize = .regular
        progressIndicator.isDisplayedWhenStopped = false
        progressIndicator.translatesAutoresizingMaskIntoConstraints = false

        statusTitle = NSTextField(labelWithString: "Recherche de KuloNiku…")
        statusTitle.font = .systemFont(ofSize: 18, weight: .semibold)
        statusMessage = NSTextField(wrappingLabelWithString: "Aucune modification n’est effectuée pendant la vérification.")
        statusMessage.textColor = .secondaryLabelColor
        statusMessage.maximumNumberOfLines = 3
        statusMessage.lineBreakMode = .byWordWrapping
        statusMessage.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)

        let statusText = NSStackView(views: [statusTitle, statusMessage])
        statusText.orientation = .vertical
        statusText.alignment = .leading
        statusText.spacing = 5

        let iconContainer = NSView()
        iconContainer.translatesAutoresizingMaskIntoConstraints = false
        iconContainer.addSubview(statusIcon)
        iconContainer.addSubview(progressIndicator)
        NSLayoutConstraint.activate([
            iconContainer.widthAnchor.constraint(equalToConstant: 52),
            iconContainer.heightAnchor.constraint(equalToConstant: 52),
            statusIcon.centerXAnchor.constraint(equalTo: iconContainer.centerXAnchor),
            statusIcon.centerYAnchor.constraint(equalTo: iconContainer.centerYAnchor),
            progressIndicator.centerXAnchor.constraint(equalTo: iconContainer.centerXAnchor),
            progressIndicator.centerYAnchor.constraint(equalTo: iconContainer.centerYAnchor)
        ])

        let statusRow = NSStackView(views: [iconContainer, statusText])
        statusRow.orientation = .horizontal
        statusRow.alignment = .centerY
        statusRow.spacing = 18
        statusRow.translatesAutoresizingMaskIntoConstraints = false

        let statusContent = NSView()
        statusContent.addSubview(statusRow)

        statusActionButton = StatusActionButton(title: "", target: self, action: #selector(activateStatusCard))
        statusActionButton.isBordered = false
        statusActionButton.setButtonType(.momentaryChange)
        statusActionButton.isHidden = true
        statusActionButton.toolTip = "Installer le français"
        statusActionButton.setAccessibilityLabel("Installer le français")
        statusActionButton.translatesAutoresizingMaskIntoConstraints = false
        statusContent.addSubview(statusActionButton)

        let statusBox = NSBox()
        statusBox.boxType = .custom
        statusBox.cornerRadius = 10
        statusBox.borderWidth = 1
        statusBox.borderColor = .separatorColor
        statusBox.fillColor = .controlBackgroundColor
        statusBox.contentViewMargins = .zero
        statusBox.contentView = statusContent
        statusBox.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            statusRow.leadingAnchor.constraint(equalTo: statusContent.leadingAnchor, constant: 28),
            statusRow.trailingAnchor.constraint(equalTo: statusContent.trailingAnchor, constant: -28),
            statusRow.centerYAnchor.constraint(equalTo: statusContent.centerYAnchor),
            statusActionButton.leadingAnchor.constraint(equalTo: statusContent.leadingAnchor),
            statusActionButton.trailingAnchor.constraint(equalTo: statusContent.trailingAnchor),
            statusActionButton.topAnchor.constraint(equalTo: statusContent.topAnchor),
            statusActionButton.bottomAnchor.constraint(equalTo: statusContent.bottomAnchor)
        ])

        gamePathField = NSTextField(labelWithString: "Aucun jeu sélectionné")
        gamePathField.lineBreakMode = .byTruncatingMiddle
        gamePathField.toolTip = "Emplacement de KuloNiku.app"
        gamePathField.textColor = .secondaryLabelColor
        gamePathField.font = .systemFont(ofSize: 13, weight: .medium)

        chooseButton = NSButton(title: "Changer de jeu…", target: self, action: #selector(chooseGame))
        chooseButton.bezelStyle = .inline
        let gameRow = NSStackView(views: [gamePathField, chooseButton])
        gameRow.orientation = .horizontal
        gameRow.alignment = .centerY
        gameRow.spacing = 10

        analyzeButton = NSButton(title: "Revérifier", target: self, action: #selector(analyze))
        installButton = NSButton(title: "Installer le français", target: self, action: #selector(installFrench))
        installButton.keyEquivalent = "\r"
        restoreButton = NSButton(title: "Restaurer l’original…", target: self, action: #selector(restoreOriginal))
        releaseButton = NSButton(title: "Télécharger", target: self, action: #selector(openLatestRelease))
        installButton.isEnabled = false
        analyzeButton.isEnabled = false
        restoreButton.isEnabled = false

        appUpdateMessage = NSTextField(labelWithString: "Une nouvelle version de KuloNiku FR est disponible.")
        appUpdateMessage.textColor = .secondaryLabelColor
        let appUpdateSpacer = NSView()
        appUpdateSpacer.setContentHuggingPriority(.defaultLow, for: .horizontal)
        appUpdateRow = NSStackView(views: [appUpdateMessage, appUpdateSpacer, releaseButton])
        appUpdateRow.orientation = .horizontal
        appUpdateRow.alignment = .centerY
        appUpdateRow.spacing = 10
        appUpdateRow.isHidden = true

        let buttonRow = NSStackView(views: [installButton, analyzeButton, restoreButton])
        buttonRow.orientation = .horizontal
        buttonRow.spacing = 10
        buttonRow.alignment = .centerY

        advancedButton = NSButton(title: "Options avancées ▸", target: self, action: #selector(toggleAdvanced))
        advancedButton.bezelStyle = .inline

        detailsButton = NSButton(title: "Journal de logs ▸", target: self, action: #selector(toggleDetails))
        detailsButton.bezelStyle = .inline

        reviewButton = NSButton(
            title: "Réviser et corriger les traductions",
            target: self,
            action: #selector(openReviewWorkspace)
        )
        reviewButton.bezelStyle = .inline
        reviewButton.isEnabled = false
        testReviewButton = NSButton(
            title: "Importer mon fichier de correction",
            target: self,
            action: #selector(testReviewCorrections)
        )
        testReviewButton.bezelStyle = .inline
        testReviewButton.isEnabled = false
        let advancedActions = NSStackView(views: [detailsButton, reviewButton, testReviewButton])
        advancedActions.orientation = .horizontal
        advancedActions.alignment = .centerY
        advancedActions.spacing = 10

        logScroll = NSScrollView()
        logScroll.hasVerticalScroller = true
        logScroll.borderType = .bezelBorder
        logScroll.translatesAutoresizingMaskIntoConstraints = false
        logScroll.isHidden = true

        logView = NSTextView()
        logView.isEditable = false
        logView.isSelectable = true
        logView.font = .monospacedSystemFont(ofSize: 12, weight: .regular)
        logView.string = "Vérification en attente."
        logScroll.documentView = logView

        advancedStack = NSStackView(views: [advancedActions, logScroll])
        advancedStack.orientation = .vertical
        advancedStack.alignment = .leading
        advancedStack.spacing = 10
        advancedStack.isHidden = true

        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "inconnue"
        let footer = NSTextField(wrappingLabelWithString:
            "Version \(version)"
        )
        footer.textColor = .tertiaryLabelColor
        footer.font = .systemFont(ofSize: 11)

        let repositoryButton = NSButton(title: "Voir le projet sur GitHub", target: self, action: #selector(openRepository))
        repositoryButton.bezelStyle = .inline

        let footerSpacer = NSView()
        footerSpacer.setContentHuggingPriority(.defaultLow, for: .horizontal)
        let footerRow = NSStackView(views: [footer, footerSpacer, repositoryButton])
        footerRow.orientation = .horizontal
        footerRow.alignment = .centerY
        footerRow.spacing = 10

        let primaryStack = NSStackView(views: [title, statusBox, appUpdateRow, gameRow, buttonRow])
        primaryStack.orientation = .vertical
        primaryStack.alignment = .leading
        primaryStack.spacing = 18

        let flexibleSpace = NSView()
        flexibleSpace.setContentHuggingPriority(.defaultLow, for: .vertical)
        flexibleSpace.setContentCompressionResistancePriority(.defaultLow, for: .vertical)

        let utilityStack = NSStackView(views: [advancedButton, advancedStack, footerRow])
        utilityStack.orientation = .vertical
        utilityStack.alignment = .leading
        utilityStack.spacing = 18

        let stack = NSStackView(views: [primaryStack, flexibleSpace, utilityStack])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 0
        stack.translatesAutoresizingMaskIntoConstraints = false
        content.addSubview(stack)

        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: content.leadingAnchor, constant: 32),
            stack.trailingAnchor.constraint(equalTo: content.trailingAnchor, constant: -32),
            stack.topAnchor.constraint(equalTo: content.topAnchor, constant: 30),
            statusIcon.widthAnchor.constraint(equalToConstant: 48),
            statusIcon.heightAnchor.constraint(equalToConstant: 48),
            progressIndicator.widthAnchor.constraint(equalToConstant: 24),
            primaryStack.widthAnchor.constraint(equalTo: stack.widthAnchor),
            utilityStack.widthAnchor.constraint(equalTo: stack.widthAnchor),
            flexibleSpace.heightAnchor.constraint(equalToConstant: 44),
            statusBox.widthAnchor.constraint(equalTo: primaryStack.widthAnchor),
            statusBox.heightAnchor.constraint(equalToConstant: 154),
            appUpdateRow.widthAnchor.constraint(equalTo: primaryStack.widthAnchor),
            gameRow.widthAnchor.constraint(equalTo: primaryStack.widthAnchor),
            advancedStack.widthAnchor.constraint(equalTo: utilityStack.widthAnchor),
            advancedActions.widthAnchor.constraint(equalTo: advancedStack.widthAnchor),
            logScroll.widthAnchor.constraint(equalTo: advancedStack.widthAnchor),
            logScroll.heightAnchor.constraint(equalToConstant: 210),
            footerRow.widthAnchor.constraint(equalTo: utilityStack.widthAnchor),
            stack.bottomAnchor.constraint(lessThanOrEqualTo: content.bottomAnchor, constant: -24)
        ])
    }

    private func selectDefaultInstallationIfAvailable() {
        if let candidate = installedGameCandidates().first {
            setSelectedGame(candidate)
            DispatchQueue.main.async { [weak self] in
                self?.analyze()
            }
        } else {
            logView.string = "KuloNiku n’a pas été trouvé automatiquement. Cliquez sur « Choisir KuloNiku.app… »."
            setStatus(
                symbol: "questionmark.folder",
                color: .systemOrange,
                title: "Jeu introuvable automatiquement",
                message: "Indiquez exceptionnellement l’application KuloNiku.app."
            )
        }
    }

    private func installedGameCandidates() -> [URL] {
        let fileManager = FileManager.default
        let home = fileManager.homeDirectoryForCurrentUser
        let steamRoot = home.appendingPathComponent("Library/Application Support/Steam")
        var libraryRoots = [steamRoot]

        for relativePath in ["steamapps/libraryfolders.vdf", "config/libraryfolders.vdf"] {
            let configuration = steamRoot.appendingPathComponent(relativePath)
            guard let text = try? String(contentsOf: configuration, encoding: .utf8) else { continue }
            let expression = try? NSRegularExpression(pattern: #"\"path\"\s+\"([^\"]+)\""#)
            let range = NSRange(text.startIndex..<text.endIndex, in: text)
            for match in expression?.matches(in: text, range: range) ?? [] {
                guard let pathRange = Range(match.range(at: 1), in: text) else { continue }
                let path = String(text[pathRange]).replacingOccurrences(of: "\\\\", with: "\\")
                libraryRoots.append(URL(fileURLWithPath: path, isDirectory: true))
            }
        }

        var candidates: [URL] = []
        for root in libraryRoots {
            let common = root.appendingPathComponent("steamapps/common", isDirectory: true)
            candidates.append(contentsOf: gameApplications(inside: common))
        }
        candidates.append(contentsOf: gameApplications(inside: URL(fileURLWithPath: "/Applications", isDirectory: true)))
        candidates.append(contentsOf: gameApplications(inside: home.appendingPathComponent("Applications", isDirectory: true)))

        var unique: [String: URL] = [:]
        for candidate in candidates where isValidGameApplication(candidate) {
            unique[candidate.standardizedFileURL.path] = candidate.standardizedFileURL
        }
        return unique.values.sorted { left, right in
            let leftDemo = left.path.lowercased().contains("demo")
            let rightDemo = right.path.lowercased().contains("demo")
            if leftDemo != rightDemo { return !leftDemo }
            return left.path.localizedStandardCompare(right.path) == .orderedAscending
        }
    }

    private func gameApplications(inside directory: URL) -> [URL] {
        let fileManager = FileManager.default
        guard let entries = try? fileManager.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles]
        ) else { return [] }

        var applications: [URL] = []
        for entry in entries where entry.lastPathComponent.lowercased().contains("kuloniku") {
            if entry.pathExtension.lowercased() == "app" {
                applications.append(entry)
                continue
            }
            guard let children = try? fileManager.contentsOfDirectory(
                at: entry,
                includingPropertiesForKeys: nil,
                options: [.skipsHiddenFiles]
            ) else { continue }
            applications.append(contentsOf: children.filter { $0.pathExtension.lowercased() == "app" })
        }
        return applications
    }

    private func isValidGameApplication(_ application: URL) -> Bool {
        FileManager.default.fileExists(
            atPath: application.appendingPathComponent("Contents/Resources/Data/resources.assets").path
        )
    }

    @objc private func openRepository() {
        NSWorkspace.shared.open(repositoryURL)
    }

    @objc private func showAbout() {
        let credits = NSMutableAttributedString(
            string: "Patch français communautaire non officiel.\n\nAucun fichier complet du jeu n’est distribué.\ngithub.com/Le-Moulin/KuloNiku-FR"
        )
        credits.addAttribute(
            .foregroundColor,
            value: NSColor.secondaryLabelColor,
            range: NSRange(location: 0, length: credits.length)
        )
        NSApplication.shared.orderFrontStandardAboutPanel(options: [
            .applicationName: "KuloNiku FR",
            .applicationVersion: currentVersion,
            .credits: credits
        ])
    }

    @objc private func openLatestRelease() {
        if let latestReleaseURL {
            NSWorkspace.shared.open(latestReleaseURL)
        }
    }

    private func refreshWindowSize() {
        var height: CGFloat = 440
        if advancedVisible { height += 55 }
        if advancedVisible && detailsVisible { height += 230 }
        window.setContentSize(NSSize(width: 760, height: height))
    }

    @objc private func toggleAdvanced() {
        advancedVisible.toggle()
        advancedStack.isHidden = !advancedVisible
        advancedButton.title = advancedVisible ? "Options avancées ▾" : "Options avancées ▸"
        refreshWindowSize()
    }

    @objc private func toggleDetails() {
        detailsVisible.toggle()
        logScroll.isHidden = !detailsVisible
        detailsButton.title = detailsVisible
            ? "Journal de logs ▾"
            : "Journal de logs ▸"
        refreshWindowSize()
    }

    @objc private func chooseGame() {
        let panel = NSOpenPanel()
        panel.title = "Choisir KuloNiku.app"
        panel.prompt = "Choisir"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.treatsFilePackagesAsDirectories = false
        panel.directoryURL = selectedGameURL?.deletingLastPathComponent()

        if panel.runModal() == .OK, let url = panel.url {
            setSelectedGame(url)
        }
    }

    private func setSelectedGame(_ url: URL) {
        selectedGameURL = url
        simulationSucceeded = false
        let edition = url.path.lowercased().contains("demo") ? "Démo détectée" : "Jeu complet détecté"
        let origin = url.path.lowercased().contains("steam") ? "Steam" : "installation locale"
        gamePathField.stringValue = "\(edition) · \(origin)"
        gamePathField.toolTip = url.path
        logView.string = "Jeu sélectionné. Vérification en attente."
        analyzeButton.isEnabled = true
        reviewButton.isEnabled = true
        testReviewButton.isEnabled = true
        installButton.isEnabled = false
        installButton.isHidden = false
        restoreButton.isEnabled = false
        restoreAvailable = false
    }

    @objc private func openReviewWorkspace() {
        guard let game = selectedGameURL else { return }
        let context = reviewContextDirectory
        let output = reviewWorkspaceOutputURL
        setBusy(
            true,
            title: "Préparation de l’espace de relecture…",
            subtitle: "Les textes restent sur ce Mac et le jeu n’est pas modifié.",
            details: "Création de l’espace de relecture en cours…"
        )
        runPatcher(arguments: [
            "review-workspace",
            game.path,
            "--translations", translationsURL.path,
            "--review-notes", context.appendingPathComponent("review-overrides.csv").path,
            "--terminology", context.appendingPathComponent("TERMINOLOGY.md").path,
            "--brief", context.appendingPathComponent("AGENT_BRIEF.md").path,
            "--output", output.path
        ]) { [weak self] result in
            guard let self else { return }
            self.setBusy(false, details: result.output)
            guard result.status == 0, FileManager.default.fileExists(atPath: output.path) else {
                self.setStatus(
                    symbol: "exclamationmark.triangle.fill",
                    color: .systemOrange,
                    title: "Création impossible",
                    message: "Consultez les détails techniques pour identifier le problème."
                )
                return
            }
            NSWorkspace.shared.open(output)
            self.setStatus(
                symbol: "doc.text.magnifyingglass",
                color: .systemTeal,
                title: "Espace de relecture ouvert",
                message: "Vous pouvez explorer les textes et préparer des corrections dans votre navigateur."
            )
        }
    }

    @objc private func testReviewCorrections() {
        guard selectedGameURL != nil else { return }
        let panel = NSOpenPanel()
        panel.title = "Choisir les propositions exportées"
        panel.prompt = "Tester"
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [.commaSeparatedText]
        guard panel.runModal() == .OK, let proposals = panel.url else { return }
        prepareReviewTest(from: proposals)
    }

    private func prepareReviewTest(from proposals: URL) {
        guard let game = selectedGameURL else { return }
        let output = reviewTestOutputURL
        setBusy(
            true,
            title: "Préparation du test…",
            subtitle: "Le fichier est contrôlé avant toute modification du jeu.",
            details: "Contrôle des corrections en cours…"
        )
        runPatcher(arguments: [
            "prepare-review-test",
            game.path,
            proposals.path,
            "--translations", translationsURL.path,
            "--output", output.path
        ]) { [weak self] preparation in
            guard let self else { return }
            guard preparation.status == 0, FileManager.default.fileExists(atPath: output.path) else {
                self.setBusy(false, details: preparation.output)
                self.setStatus(
                    symbol: "exclamationmark.triangle.fill",
                    color: .systemOrange,
                    title: "Corrections non testables",
                    message: "Le fichier ne correspond pas aux textes actuels ou contient des marqueurs invalides."
                )
                return
            }
            let simulationArguments = [
                "install", game.path, "--translations", output.path
            ]
            self.runPatcher(arguments: simulationArguments) { [weak self] simulation in
                guard let self else { return }
                let details = preparation.output + "\n\n--- Simulation ---\n" + simulation.output
                self.setBusy(false, details: details)
                guard simulation.status == 0 else {
                    self.setStatus(
                        symbol: "exclamationmark.triangle.fill",
                        color: .systemOrange,
                        title: "Test indisponible",
                        message: "La simulation a échoué. Le jeu n’a pas été modifié."
                    )
                    return
                }
                let alert = NSAlert()
                alert.messageText = "Installer ces corrections dans le jeu ?"
                alert.informativeText = "La sauvegarde originale vérifiée sera créée ou conservée."
                alert.alertStyle = .informational
                alert.addButton(withTitle: "Installer pour tester")
                alert.addButton(withTitle: "Annuler")
                guard alert.runModal() == .alertFirstButtonReturn else {
                    self.setStatus(
                        symbol: "doc.text.magnifyingglass",
                        color: .systemTeal,
                        title: "Corrections prêtes à tester",
                        message: "Aucune modification n’a été effectuée."
                    )
                    return
                }
                self.installReviewTest(
                    arguments: simulationArguments + ["--apply"],
                    previousDetails: details
                )
            }
        }
    }

    private func installReviewTest(arguments: [String], previousDetails: String) {
        setBusy(
            true,
            title: "Installation des corrections…",
            subtitle: "Ne fermez pas cette fenêtre.",
            details: previousDetails
        )
        runPatcher(arguments: arguments) { [weak self] result in
            guard let self else { return }
            self.setBusy(
                false,
                details: previousDetails + "\n\n--- Installation ---\n" + result.output
            )
            if result.status == 0 {
                self.restoreAvailable = true
                self.restoreButton.isEnabled = true
                self.simulationSucceeded = false
                self.installButton.isEnabled = false
                self.installButton.isHidden = true
                self.setStatus(
                    symbol: "checkmark.circle.fill",
                    color: .systemGreen,
                    title: "Corrections installées pour test",
                    message: "Lancez le jeu et vérifiez les passages concernés."
                )
                self.showCompletion(
                    success: true,
                    title: "Corrections prêtes à tester",
                    message: "Lancez KuloNiku depuis Steam. Vous pourrez restaurer l’original ou réinstaller la traduction publique ensuite."
                )
            } else {
                self.setStatus(
                    symbol: "exclamationmark.triangle.fill",
                    color: .systemOrange,
                    title: "Installation impossible",
                    message: "Le jeu reste protégé. Consultez les détails techniques."
                )
            }
        }
    }

    @objc private func analyze() {
        guard let game = selectedGameURL else { return }
        simulationSucceeded = false
        setBusy(
            true,
            title: "Vérification du jeu…",
            subtitle: "Contrôle de la version, de la sauvegarde et des traductions.",
            details: "Analyse en cours…"
        )
        runPatcher(arguments: ["status", game.path, "--translations", translationsURL.path, "--json"]) { [weak self] result in
            guard let self else { return }
            self.logView.string = result.output
            guard result.status == 0,
                  let data = result.output.data(using: .utf8),
                  let report = try? JSONDecoder().decode(InstallationStatus.self, from: data)
            else {
                self.setBusy(false, details: result.output)
                self.setStatus(
                    symbol: "exclamationmark.triangle.fill",
                    color: .systemOrange,
                    title: "Vérification impossible",
                    message: "Le jeu n’a pas été modifié. Les détails techniques peuvent aider au diagnostic."
                )
                return
            }

            self.restoreAvailable = report.backupAvailable
            let origin = game.path.lowercased().contains("steam") ? "Steam" : "installation locale"
            self.gamePathField.stringValue = report.edition == "demo"
                ? "Démo détectée · \(origin)"
                : "Jeu complet détecté · \(origin)"

            if report.state == "patched" && report.translationState == "current" {
                self.setBusy(false, details: result.output)
                self.installButton.title = "Traduction à jour"
                self.installButton.isEnabled = false
                self.installButton.isHidden = true
                self.setStatus(
                    symbol: "checkmark.circle.fill",
                    color: .systemGreen,
                    title: "Installation propre et à jour",
                    message: "La traduction française installée correspond exactement à cette version."
                )
            } else {
                let isUpdate = report.state == "patched"
                self.validateInstall(
                    isUpdate: isUpdate || report.state == "game_updated",
                    sourceRecognition: report.sourceRecognition,
                    previousDetails: result.output
                )
            }
            self.checkLatestRelease(
                edition: report.edition,
                bundledTranslationHash: report.availableBundleSHA256
            )
        }
    }

    private func validateInstall(isUpdate: Bool, sourceRecognition: String?, previousDetails: String) {
        guard let game = selectedGameURL else { return }
        runPatcher(arguments: ["install", game.path, "--translations", translationsURL.path]) { [weak self] result in
            guard let self else { return }
            let details = previousDetails + "\n\n" + result.output
            self.simulationSucceeded = result.status == 0
            self.setBusy(false, details: details)
            self.installButton.title = isUpdate ? "Mettre à jour le français" : "Installer le français"
            self.installButton.isHidden = false
            self.installButton.isEnabled = self.simulationSucceeded
            if self.simulationSucceeded {
                let unlistedVersion = sourceRecognition == "unknown"
                self.setStatus(
                    symbol: isUpdate ? "arrow.down.circle.fill" : "plus.circle.fill",
                    color: .systemBlue,
                    title: unlistedVersion
                        ? "Version récente, français disponible"
                        : (isUpdate ? "Mise à jour française disponible" : "Prêt à installer le français"),
                    message: unlistedVersion
                        ? "Cette version du jeu n’a pas encore été testée. Les textes sans français compatible resteront en anglais."
                        : (isUpdate
                            ? "Une traduction embarquée plus récente peut être appliquée sans restauration préalable."
                            : "Le jeu est compatible. Une sauvegarde vérifiée sera créée avant l’installation."),
                    cardActionEnabled: true
                )
            } else {
                self.setStatus(
                    symbol: "exclamationmark.triangle.fill",
                    color: .systemOrange,
                    title: "Action indisponible",
                    message: "Aucune modification n’a été faite. Consultez les détails techniques si nécessaire."
                )
            }
        }
    }

    @objc private func installFrench() {
        guard let game = selectedGameURL, simulationSucceeded else { return }
        let isUpdate = installButton.title.contains("Mettre à jour")
        let actionName = isUpdate ? "Mettre à jour" : "Installer"

        let alert = NSAlert()
        alert.messageText = isUpdate
            ? "Mettre à jour la traduction française ?"
            : "Installer la traduction française ?"
        alert.informativeText = isUpdate
            ? "La sauvegarde originale vérifiée sera conservée. Aucune restauration manuelle n’est nécessaire."
            : "Une sauvegarde vérifiée sera créée avant toute modification."
        alert.alertStyle = .informational
        alert.addButton(withTitle: actionName)
        alert.addButton(withTitle: "Annuler")
        guard alert.runModal() == .alertFirstButtonReturn else { return }

        setBusy(
            true,
            title: isUpdate ? "Mise à jour du français…" : "Installation du français…",
            subtitle: "Le jeu est en cours de préparation. Ne fermez pas cette fenêtre.",
            details: isUpdate ? "Mise à jour en cours…" : "Installation en cours…"
        )
        runPatcher(arguments: ["install", game.path, "--translations", translationsURL.path, "--apply"]) { [weak self] result in
            guard let self else { return }
            self.simulationSucceeded = false
            self.setBusy(false, details: result.output)
            self.installButton.isEnabled = false
            self.installButton.isHidden = result.status == 0
            if result.status == 0 {
                self.restoreAvailable = true
                self.restoreButton.isEnabled = true
            }
            self.setStatus(
                symbol: result.status == 0 ? "checkmark.circle.fill" : "exclamationmark.triangle.fill",
                color: result.status == 0 ? .systemGreen : .systemOrange,
                title: result.status == 0
                    ? "Installation propre et à jour"
                    : (isUpdate ? "Mise à jour impossible" : "Installation impossible"),
                message: result.status == 0
                    ? "La traduction française est installée et sa sauvegarde originale est vérifiée."
                    : "Le jeu reste protégé. Consultez les détails techniques."
            )
            self.showCompletion(
                success: result.status == 0,
                title: result.status == 0
                    ? (isUpdate ? "Traduction mise à jour" : "Traduction installée")
                    : (isUpdate ? "Mise à jour impossible" : "Installation impossible"),
                message: result.status == 0
                    ? "Relancez le jeu depuis Steam et choisissez Français dans les paramètres."
                    : "Aucun changement incomplet ne doit rester. Consultez le diagnostic affiché."
            )
        }
    }

    @objc private func activateStatusCard() {
        installFrench()
    }

    @objc private func restoreOriginal() {
        guard let game = selectedGameURL else { return }
        setBusy(
            true,
            title: "Vérification de la sauvegarde…",
            subtitle: "Contrôle de son intégrité avant de proposer la restauration.",
            details: "Vérification de la sauvegarde…"
        )
        runPatcher(arguments: ["restore", game.path]) { [weak self] simulation in
            guard let self else { return }
            self.setBusy(false, details: simulation.output)
            guard simulation.status == 0 else {
                self.setStatus(
                    symbol: "exclamationmark.triangle.fill",
                    color: .systemOrange,
                    title: "Restauration indisponible",
                    message: "Aucune sauvegarde vérifiée n’a été trouvée."
                )
                self.showCompletion(success: false, title: "Restauration impossible", message: "Aucune sauvegarde restaurable n’a été trouvée.")
                return
            }

            self.setStatus(
                symbol: "arrow.uturn.backward.circle.fill",
                color: .systemBlue,
                title: "Sauvegarde prête à restaurer",
                message: "La traduction française sera retirée et le fichier original rétabli."
            )

            let alert = NSAlert()
            alert.messageText = "Restaurer le fichier original ?"
            alert.informativeText = "La traduction française sera retirée. Vous pourrez la réinstaller plus tard."
            alert.alertStyle = .warning
            alert.addButton(withTitle: "Restaurer")
            alert.addButton(withTitle: "Annuler")
            guard alert.runModal() == .alertFirstButtonReturn else { return }

            self.setBusy(
                true,
                title: "Restauration en cours…",
                subtitle: "Le fichier original vérifié est en cours de remise en place.",
                details: "Restauration en cours…"
            )
            self.runPatcher(arguments: ["restore", game.path, "--apply"]) { [weak self] result in
                guard let self else { return }
                self.simulationSucceeded = false
                self.setBusy(false, details: result.output)
                self.installButton.isEnabled = false
                self.setStatus(
                    symbol: result.status == 0 ? "checkmark.circle.fill" : "exclamationmark.triangle.fill",
                    color: result.status == 0 ? .systemGreen : .systemOrange,
                    title: result.status == 0 ? "Fichier original restauré" : "Restauration impossible",
                    message: result.status == 0
                        ? "La sauvegarde vérifiée a été remise en place."
                        : "Le jeu reste protégé. Consultez les détails techniques."
                )
                self.showCompletion(
                    success: result.status == 0,
                    title: result.status == 0 ? "Fichier original restauré" : "Restauration impossible",
                    message: result.status == 0
                        ? "Le jeu a retrouvé son fichier sauvegardé."
                        : "Consultez le diagnostic affiché."
                )
                if result.status == 0 {
                    self.analyze()
                }
            }
        }
    }

    private func setStatus(
        symbol: String?,
        color: NSColor,
        title: String,
        message: String,
        cardActionEnabled: Bool = false
    ) {
        let displayedTitle = installerUpdateRequired
            ? "Mise à jour de l’application requise"
            : title
        let displayedMessage = installerUpdateRequired
            ? "Le nouveau français demande cette version de KuloNiku FR."
            : message
        statusTitle.stringValue = displayedTitle
        statusMessage.stringValue = displayedMessage
        statusActionButton.isHidden = !cardActionEnabled
        statusActionButton.isEnabled = cardActionEnabled
        statusActionButton.toolTip = installButton.title
        statusActionButton.setAccessibilityLabel(installButton.title)
        statusActionButton.window?.invalidateCursorRects(for: statusActionButton)
        if let symbol {
            statusIcon.image = NSImage(
                systemSymbolName: installerUpdateRequired
                    ? "exclamationmark.arrow.triangle.2.circlepath"
                    : symbol,
                accessibilityDescription: displayedTitle
            )
            statusIcon.contentTintColor = installerUpdateRequired ? .systemOrange : color
            statusIcon.isHidden = false
        } else {
            statusIcon.image = nil
            statusIcon.isHidden = true
        }
    }

    private func checkLatestRelease(
        edition: String? = nil,
        bundledTranslationHash: String? = nil
    ) {
        latestReleaseURL = nil
        appUpdateRow.isHidden = true
        guard let apiURL = URL(string: "https://api.github.com/repos/Le-Moulin/KuloNiku-FR/releases?per_page=10") else { return }
        var request = URLRequest(url: apiURL)
        request.setValue("KuloNiku-FR/\(currentVersion)", forHTTPHeaderField: "User-Agent")
        request.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")

        URLSession.shared.dataTask(with: request) { [weak self] data, response, _ in
            guard let self,
                  let http = response as? HTTPURLResponse,
                  http.statusCode == 200,
                  let data,
                  let releases = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]],
                  let object = releases.first(where: { release in
                      isPrereleaseVersion(self.currentVersion)
                          || !((release["prerelease"] as? Bool) ?? false)
                  }),
                  let page = object["html_url"] as? String,
                  let pageURL = URL(string: page),
                  let assets = object["assets"] as? [[String: Any]],
                  let manifestAsset = assets.first(where: { ($0["name"] as? String) == "update-manifest.json" }),
                  let manifestDownload = manifestAsset["browser_download_url"] as? String,
                  let manifestURL = URL(string: manifestDownload)
            else { return }

            URLSession.shared.dataTask(with: manifestURL) { [weak self] data, _, _ in
                guard let self,
                      let data,
                      let manifest = try? JSONDecoder().decode(UpdateManifest.self, from: data)
                else { return }
                let engineUpdateAvailable = isVersion(
                    manifest.version,
                    newerThan: self.currentVersion
                )

                if engineUpdateAvailable {
                    DispatchQueue.main.async {
                        self.latestReleaseURL = pageURL
                        self.appUpdateMessage.stringValue = "KuloNiku FR \(manifest.version) est disponible."
                        self.releaseButton.title = "Télécharger"
                        self.appUpdateRow.isHidden = false
                        self.appendLog(
                            "\n\nNouvelle version de l’application disponible : \(manifest.version)."
                        )
                    }
                }

                guard let edition,
                      let bundledTranslationHash
                else { return }

                if let package = newerTranslationPackage(
                    in: manifest,
                    edition: edition,
                    activeVersion: self.downloadedTranslationsVersion ?? self.currentVersion,
                    activeHash: bundledTranslationHash
                ),
                   let expectedHash = package.bundles[edition] {
                    if isVersion(
                        package.minimumPatcherVersion,
                        newerThan: self.currentVersion
                    ) {
                        DispatchQueue.main.async {
                            self.installerUpdateRequired = true
                            self.latestReleaseURL = pageURL
                            self.appUpdateMessage.stringValue = "KuloNiku FR \(package.minimumPatcherVersion) est requis."
                            self.releaseButton.title = "Télécharger"
                            self.appUpdateRow.isHidden = false
                            self.releaseButton.keyEquivalent = "\r"
                            self.installButton.isHidden = true
                            self.installButton.keyEquivalent = ""
                            self.setStatus(
                                symbol: "exclamationmark.arrow.triangle.2.circlepath",
                                color: .systemOrange,
                                title: "Mise à jour de l’application requise",
                                message: "Le nouveau français demande cette version de KuloNiku FR."
                            )
                            self.appendLog(
                                "\n\nCette traduction demande KuloNiku FR \(package.minimumPatcherVersion) ou plus récent."
                            )
                        }
                        return
                    }
                    guard let packageAsset = assets.first(where: {
                        ($0["name"] as? String) == package.asset
                    }),
                    let packageDownload = packageAsset["browser_download_url"] as? String,
                    let packageURL = URL(string: packageDownload)
                    else { return }
                    self.downloadTranslationPackage(
                        package,
                        from: packageURL,
                        expectedBundleHash: expectedHash,
                        edition: edition,
                        releaseURL: pageURL
                    )
                }
            }.resume()
        }.resume()
    }

    private func downloadTranslationPackage(
        _ package: TranslationPackage,
        from remoteURL: URL,
        expectedBundleHash: String,
        edition: String,
        releaseURL: URL
    ) {
        DispatchQueue.main.async {
            guard !self.translationDownloadInProgress else { return }
            self.translationDownloadInProgress = true
            self.appendLog("\n\nTéléchargement de la traduction française \(package.version)…")

            let cacheDirectory = self.translationCacheDirectory
                .appendingPathComponent(package.sha256, isDirectory: true)
            let cachedFrench = cacheDirectory.appendingPathComponent("fr.csv")
            if FileManager.default.isReadableFile(atPath: cachedFrench.path) {
                self.validateDownloadedTranslations(
                    cachedFrench,
                    packageVersion: package.version,
                    expectedBundleHash: expectedBundleHash,
                    edition: edition,
                    releaseURL: releaseURL
                )
                return
            }

            URLSession.shared.downloadTask(with: remoteURL) { [weak self] temporaryArchive, _, _ in
                guard let self else { return }
                guard let temporaryArchive else {
                    DispatchQueue.main.async {
                        self.translationDownloadFailed(releaseURL: releaseURL)
                    }
                    return
                }
                do {
                    guard try self.sha256(of: temporaryArchive) == package.sha256.lowercased() else {
                        throw NSError(
                            domain: "KuloNikuFR",
                            code: 1,
                            userInfo: [NSLocalizedDescriptionKey: "L’empreinte du paquet ne correspond pas."]
                        )
                    }
                    let fileManager = FileManager.default
                    try fileManager.createDirectory(
                        at: self.translationCacheDirectory,
                        withIntermediateDirectories: true
                    )
                    let extraction = self.translationCacheDirectory
                        .appendingPathComponent(".download-\(UUID().uuidString)", isDirectory: true)
                    try fileManager.createDirectory(at: extraction, withIntermediateDirectories: false)
                    defer { try? fileManager.removeItem(at: extraction) }

                    let ditto = Process()
                    ditto.executableURL = URL(fileURLWithPath: "/usr/bin/ditto")
                    ditto.arguments = ["-x", "-k", temporaryArchive.path, extraction.path]
                    try ditto.run()
                    ditto.waitUntilExit()
                    guard ditto.terminationStatus == 0 else {
                        throw NSError(
                            domain: "KuloNikuFR",
                            code: 2,
                            userInfo: [NSLocalizedDescriptionKey: "Le paquet n’a pas pu être ouvert."]
                        )
                    }
                    for name in ["fr.csv", "source-hashes.csv", "demo-overrides.csv", "known-sources.json", "full-overrides.csv", "native-approvals.csv"] {
                        guard fileManager.isReadableFile(atPath: extraction.appendingPathComponent(name).path) else {
                            throw NSError(
                                domain: "KuloNikuFR",
                                code: 3,
                                userInfo: [NSLocalizedDescriptionKey: "Le paquet de traduction est incomplet."]
                            )
                        }
                    }
                    if fileManager.fileExists(atPath: cacheDirectory.path) {
                        try fileManager.removeItem(at: cacheDirectory)
                    }
                    try fileManager.moveItem(at: extraction, to: cacheDirectory)
                    DispatchQueue.main.async {
                        self.validateDownloadedTranslations(
                            cacheDirectory.appendingPathComponent("fr.csv"),
                            packageVersion: package.version,
                            expectedBundleHash: expectedBundleHash,
                            edition: edition,
                            releaseURL: releaseURL
                        )
                    }
                } catch {
                    DispatchQueue.main.async {
                        self.appendLog("\nÉchec du téléchargement : \(error.localizedDescription)")
                        self.translationDownloadFailed(releaseURL: releaseURL)
                    }
                }
            }.resume()
        }
    }

    private func validateDownloadedTranslations(
        _ candidate: URL,
        packageVersion: String,
        expectedBundleHash: String,
        edition: String,
        releaseURL: URL
    ) {
        guard let game = selectedGameURL else {
            translationDownloadInProgress = false
            return
        }
        runPatcher(arguments: ["status", game.path, "--translations", candidate.path, "--json"]) { [weak self] result in
            guard let self else { return }
            guard result.status == 0,
                  isVersion(packageVersion, newerThan: self.downloadedTranslationsVersion ?? self.currentVersion),
                  let data = result.output.data(using: .utf8),
                  let report = try? JSONDecoder().decode(InstallationStatus.self, from: data),
                  report.edition == edition,
                  report.availableBundleSHA256 == expectedBundleHash
            else {
                self.translationDownloadFailed(releaseURL: releaseURL)
                return
            }
            self.translationDownloadInProgress = false
            self.downloadedTranslationsURL = candidate
            self.downloadedTranslationsVersion = packageVersion
            self.appendLog("\nTraduction téléchargée et vérifiée. Elle est prête à être appliquée.")
            self.analyze()
        }
    }

    private func translationDownloadFailed(releaseURL: URL) {
        translationDownloadInProgress = false
        latestReleaseURL = releaseURL
        appUpdateMessage.stringValue = "Le téléchargement automatique est indisponible."
        releaseButton.title = "Voir sur GitHub"
        appUpdateRow.isHidden = false
        appendLog("\nLa traduction locale reste inchangée.")
    }

    private func sha256(of url: URL) throws -> String {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        var hasher = SHA256()
        while true {
            let data = try handle.read(upToCount: 1024 * 1024) ?? Data()
            if data.isEmpty { break }
            hasher.update(data: data)
        }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }

    private var currentVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0"
    }

    private var patcherURL: URL {
        Bundle.main.resourceURL!.appendingPathComponent(bundledPatcherExecutable)
    }

    private var translationsURL: URL {
        downloadedTranslationsURL
            ?? Bundle.main.resourceURL!.appendingPathComponent("translations/fr.csv")
    }

    private var translationCacheDirectory: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("KuloNiku FR/translations", isDirectory: true)
    }

    private var reviewWorkspaceOutputURL: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("KuloNiku FR/review-workspace/index.html")
    }

    private var reviewTestOutputURL: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("KuloNiku FR/review-test/fr.csv")
    }

    private var reviewContextDirectory: URL {
        let active = translationsURL.deletingLastPathComponent()
        let required = ["review-overrides.csv", "TERMINOLOGY.md", "AGENT_BRIEF.md"]
        if required.allSatisfy({
            FileManager.default.fileExists(atPath: active.appendingPathComponent($0).path)
        }) {
            return active
        }
        return Bundle.main.resourceURL!.appendingPathComponent("translations", isDirectory: true)
    }

    private func runPatcher(arguments: [String], completion: @escaping ((status: Int32, output: String)) -> Void) {
        let patcher = patcherURL
        guard FileManager.default.isExecutableFile(atPath: patcher.path) else {
            completion((1, "Erreur : le moteur intégré est introuvable ou non exécutable."))
            return
        }

        DispatchQueue.global(qos: .userInitiated).async {
            let task = Process()
            let pipe = Pipe()
            task.executableURL = patcher
            task.arguments = arguments
            task.standardOutput = pipe
            task.standardError = pipe
            task.currentDirectoryURL = Bundle.main.resourceURL

            do {
                try task.run()
                task.waitUntilExit()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                let output = String(data: data, encoding: .utf8) ?? "Sortie illisible."
                DispatchQueue.main.async {
                    completion((task.terminationStatus, output.trimmingCharacters(in: .whitespacesAndNewlines)))
                }
            } catch {
                DispatchQueue.main.async {
                    completion((1, "Impossible de lancer le moteur : \(error.localizedDescription)"))
                }
            }
        }
    }

    private func setBusy(
        _ busy: Bool,
        title: String? = nil,
        subtitle: String? = nil,
        details: String
    ) {
        chooseButton.isEnabled = !busy
        analyzeButton.isEnabled = !busy && selectedGameURL != nil
        reviewButton.isEnabled = !busy && selectedGameURL != nil
        testReviewButton.isEnabled = !busy && selectedGameURL != nil
        restoreButton.isEnabled = !busy && restoreAvailable
        installButton.isEnabled = !busy && simulationSucceeded
        releaseButton.isEnabled = !busy
        if busy {
            setStatus(
                symbol: nil,
                color: .secondaryLabelColor,
                title: title ?? "Opération en cours…",
                message: subtitle ?? "Merci de patienter."
            )
            progressIndicator.startAnimation(nil)
        } else {
            progressIndicator.stopAnimation(nil)
        }
        logView.string = details
    }

    private func appendLog(_ message: String) {
        logView.string += message
        logView.scrollToEndOfDocument(nil)
    }

    private func showCompletion(success: Bool, title: String, message: String) {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = message
        alert.alertStyle = success ? .informational : .warning
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }
}

if CommandLine.arguments.contains("--self-test-updates") {
    exit(runUpdatePolicySelfTest())
} else if CommandLine.arguments.contains("--self-test") {
    exit(runLauncherSelfTest())
} else {
    let application = NSApplication.shared
    let applicationDelegate = AppDelegate()
    application.delegate = applicationDelegate
    application.run()
}
