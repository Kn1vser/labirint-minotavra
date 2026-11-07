-- Интерфейс игрока «Небоскрёб Тайкун».
-- Весь GUI создаётся кодом, поэтому ничего рисовать в Studio не нужно.
-- Работает и на ПК, и на телефоне.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")
local MarketplaceService = game:GetService("MarketplaceService")
local RunService = game:GetService("RunService")

local player = Players.LocalPlayer
local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared:WaitForChild("Config"))
local Format = require(Shared:WaitForChild("Format"))

local Remotes = ReplicatedStorage:WaitForChild("Remotes")
local BuildFloor = Remotes:WaitForChild("BuildFloor") :: RemoteEvent
local Collect = Remotes:WaitForChild("Collect") :: RemoteEvent
local BuyUpgrade = Remotes:WaitForChild("BuyUpgrade") :: RemoteEvent
local Repair = Remotes:WaitForChild("Repair") :: RemoteEvent
local Rebirth = Remotes:WaitForChild("Rebirth") :: RemoteEvent
local RequestState = Remotes:WaitForChild("RequestState") :: RemoteEvent
local StateUpdate = Remotes:WaitForChild("StateUpdate") :: RemoteEvent
local Notify = Remotes:WaitForChild("Notify") :: RemoteEvent
local ClaimDaily = Remotes:WaitForChild("ClaimDaily") :: RemoteEvent
local RedeemCode = Remotes:WaitForChild("RedeemCode") :: RemoteEvent

---------------------------------------------------------------------
-- Цвета и помощники
---------------------------------------------------------------------
local COLORS = {
	Panel = Color3.fromRGB(24, 27, 40),
	PanelLight = Color3.fromRGB(38, 42, 60),
	Text = Color3.fromRGB(245, 245, 250),
	Muted = Color3.fromRGB(160, 165, 185),
	Gold = Color3.fromRGB(255, 205, 60),
	Green = Color3.fromRGB(70, 200, 110),
	Red = Color3.fromRGB(225, 75, 75),
	Blue = Color3.fromRGB(70, 140, 255),
	Purple = Color3.fromRGB(150, 90, 230),
	Orange = Color3.fromRGB(240, 140, 50),
}

local function create(className: string, props: { [string]: any }, children: { Instance }?): any
	local instance = Instance.new(className)
	for key, value in pairs(props) do
		if key ~= "Parent" then
			(instance :: any)[key] = value
		end
	end
	if children then
		for _, child in children do
			child.Parent = instance
		end
	end
	if props.Parent then
		instance.Parent = props.Parent
	end
	return instance
end

local function corner(radius: number?): UICorner
	return create("UICorner", { CornerRadius = UDim.new(0, radius or 12) })
end

local function stroke(color: Color3?, thickness: number?): UIStroke
	return create("UIStroke", {
		Color = color or Color3.fromRGB(70, 75, 100),
		Thickness = thickness or 2,
		ApplyStrokeMode = Enum.ApplyStrokeMode.Border,
	})
end

local function padding(px: number): UIPadding
	local p = UDim.new(0, px)
	return create("UIPadding", { PaddingTop = p, PaddingBottom = p, PaddingLeft = p, PaddingRight = p })
end

local function label(props: { [string]: any }): TextLabel
	local defaults = {
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamBold,
		TextColor3 = COLORS.Text,
		TextScaled = true,
		Text = "",
	}
	for key, value in pairs(props) do
		defaults[key] = value
	end
	return create("TextLabel", defaults)
end

local function button(props: { [string]: any }, color: Color3): TextButton
	local defaults = {
		BackgroundColor3 = color,
		Font = Enum.Font.GothamBold,
		TextColor3 = COLORS.Text,
		TextScaled = true,
		AutoButtonColor = true,
		Text = "",
	}
	for key, value in pairs(props) do
		defaults[key] = value
	end
	local result = create("TextButton", defaults, {
		corner(10),
		create("UITextSizeConstraint", { MaxTextSize = 28 }),
	})
	return result
end

-- маленькая "пружинка" при нажатии
local function pop(guiObject: GuiObject)
	local scale = guiObject:FindFirstChildOfClass("UIScale") or create("UIScale", { Parent = guiObject })
	scale.Scale = 0.92
	TweenService:Create(scale, TweenInfo.new(0.2, Enum.EasingStyle.Back), { Scale = 1 }):Play()
end

local function playSound(id: string, volume: number?)
	local sound = create("Sound", { SoundId = id, Volume = volume or 0.5, Parent = workspace.CurrentCamera })
	sound:Play()
	sound.Ended:Once(function()
		sound:Destroy()
	end)
	task.delay(5, function()
		if sound.Parent then
			sound:Destroy()
		end
	end)
end

local SOUND_BUILD = "rbxasset://sounds/clickfast.wav"
local SOUND_MONEY = "rbxasset://sounds/electronicpingshort.wav"

---------------------------------------------------------------------
-- Главный экран
---------------------------------------------------------------------
local gui = create("ScreenGui", {
	Name = "TowerUI",
	ResetOnSpawn = false,
	ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	Parent = player:WaitForChild("PlayerGui"),
})

-- Верх: деньги и доход
local statsPanel = create("Frame", {
	AnchorPoint = Vector2.new(0.5, 0),
	Position = UDim2.new(0.5, 0, 0, 6),
	Size = UDim2.new(0.42, 0, 0.12, 0),
	BackgroundColor3 = COLORS.Panel,
	BackgroundTransparency = 0.1,
	Parent = gui,
}, {
	corner(14),
	stroke(),
	padding(6),
	create("UISizeConstraint", { MinSize = Vector2.new(260, 64), MaxSize = Vector2.new(560, 110) }),
})

local cashLabel = label({
	Size = UDim2.fromScale(1, 0.55),
	TextColor3 = COLORS.Gold,
	Text = "💰 0",
	Parent = statsPanel,
})
local infoLabel = label({
	Position = UDim2.fromScale(0, 0.58),
	Size = UDim2.fromScale(1, 0.42),
	TextColor3 = COLORS.Muted,
	Font = Enum.Font.Gotham,
	RichText = true,
	Text = "",
	Parent = statsPanel,
})

-- Слева: касса
local registerPanel = create("Frame", {
	AnchorPoint = Vector2.new(0, 0.5),
	Position = UDim2.new(0, 10, 0.4, 0),
	Size = UDim2.new(0.16, 0, 0.17, 0),
	BackgroundColor3 = COLORS.Panel,
	BackgroundTransparency = 0.1,
	Parent = gui,
}, {
	corner(14),
	stroke(COLORS.Green),
	padding(6),
	create("UISizeConstraint", { MinSize = Vector2.new(120, 80), MaxSize = Vector2.new(220, 130) }),
})
local registerLabel = label({
	Size = UDim2.fromScale(1, 0.5),
	Text = "🧾 Касса\n0",
	Parent = registerPanel,
})
local collectButton = button({
	Position = UDim2.fromScale(0, 0.55),
	Size = UDim2.fromScale(1, 0.45),
	Text = "Собрать",
	Parent = registerPanel,
}, COLORS.Green)

-- Справа: кнопки меню
local sideMenu = create("Frame", {
	AnchorPoint = Vector2.new(1, 0.5),
	Position = UDim2.new(1, -10, 0.4, 0),
	Size = UDim2.new(0.17, 0, 0.58, 0),
	BackgroundTransparency = 1,
	Parent = gui,
}, {
	create("UIListLayout", {
		Padding = UDim.new(0, 5),
		SortOrder = Enum.SortOrder.LayoutOrder,
		VerticalAlignment = Enum.VerticalAlignment.Center,
	}),
	create("UISizeConstraint", { MinSize = Vector2.new(130, 200), MaxSize = Vector2.new(240, 440) }),
})

local function sideButton(text: string, color: Color3, order: number): TextButton
	return button({
		Size = UDim2.fromScale(1, 0.15),
		Text = text,
		LayoutOrder = order,
		Parent = sideMenu,
	}, color)
end

local dailyButton = sideButton("🎁 Награда", COLORS.Gold, 0)
dailyButton.TextColor3 = Color3.fromRGB(60, 40, 0)
dailyButton.Visible = false
local upgradesButton = sideButton("⬆️ Улучшения", COLORS.Blue, 1)
local repairButton = sideButton("🔧 Ремонт", COLORS.Red, 2)
local rebirthButton = sideButton("♻️ Реконструкция", COLORS.Purple, 3)
local passButton = sideButton("⚡ x2 Доход", COLORS.Orange, 4)
repairButton.Visible = false
passButton.Visible = Config.GAMEPASS_DOUBLE_INCOME ~= 0
local codesButton = sideButton("🎟️ Коды", COLORS.PanelLight, 5)

-- Плашка «Золотой час» под деньгами
local goldenLabel = label({
	Position = UDim2.new(0, 0, 1, 10),
	Size = UDim2.new(1, 0, 0.45, 0),
	BackgroundTransparency = 0.1,
	BackgroundColor3 = Color3.fromRGB(90, 70, 10),
	TextColor3 = COLORS.Gold,
	Text = "",
	Visible = false,
	Parent = statsPanel,
})
corner(10).Parent = goldenLabel
stroke(COLORS.Gold, 2).Parent = goldenLabel

-- Низ: постройка
local buildPanel = create("Frame", {
	AnchorPoint = Vector2.new(0.5, 1),
	Position = UDim2.new(0.5, 0, 1, -8),
	Size = UDim2.new(0.5, 0, 0.27, 0),
	BackgroundColor3 = COLORS.Panel,
	BackgroundTransparency = 0.1,
	Parent = gui,
}, {
	corner(14),
	stroke(),
	padding(6),
	create("UISizeConstraint", { MinSize = Vector2.new(300, 120), MaxSize = Vector2.new(720, 220) }),
})

local buildButton = button({
	Size = UDim2.fromScale(1, 0.36),
	Text = "🔨 Построить этаж",
	Parent = buildPanel,
}, COLORS.Green)

local cardsFrame = create("ScrollingFrame", {
	Position = UDim2.fromScale(0, 0.4),
	Size = UDim2.fromScale(1, 0.6),
	BackgroundTransparency = 1,
	ScrollingDirection = Enum.ScrollingDirection.X,
	ScrollBarThickness = 4,
	AutomaticCanvasSize = Enum.AutomaticSize.X,
	CanvasSize = UDim2.new(0, 0, 0, 0),
	Parent = buildPanel,
}, {
	create("UIListLayout", {
		FillDirection = Enum.FillDirection.Horizontal,
		Padding = UDim.new(0, 6),
		SortOrder = Enum.SortOrder.LayoutOrder,
	}),
})

type Card = {
	Button: TextButton,
	Title: TextLabel,
	Income: TextLabel,
	Cost: TextLabel,
	Lock: TextLabel,
	Stroke: UIStroke,
}
local cards: { Card } = {}

for i, floorType in Config.FloorTypes do
	local cardStroke = stroke(Color3.fromRGB(70, 75, 100), 2)
	local cardButton = create("TextButton", {
		Size = UDim2.new(0, 0, 1, -6),
		BackgroundColor3 = COLORS.PanelLight,
		AutoButtonColor = true,
		Text = "",
		LayoutOrder = i,
		Parent = cardsFrame,
	}, {
		corner(10),
		cardStroke,
		create("UIAspectRatioConstraint", { AspectRatio = 1.15, DominantAxis = Enum.DominantAxis.Height }),
	})
	local card: Card = {
		Button = cardButton,
		Stroke = cardStroke,
		Title = label({
			Position = UDim2.fromScale(0.05, 0.03),
			Size = UDim2.fromScale(0.9, 0.36),
			Text = `{floorType.Emoji} {floorType.Name}`,
			Parent = cardButton,
		}),
		Income = label({
			Position = UDim2.fromScale(0.05, 0.4),
			Size = UDim2.fromScale(0.9, 0.27),
			TextColor3 = COLORS.Green,
			Text = "+0/с",
			Parent = cardButton,
		}),
		Cost = label({
			Position = UDim2.fromScale(0.05, 0.68),
			Size = UDim2.fromScale(0.9, 0.28),
			TextColor3 = COLORS.Gold,
			Text = "💰 0",
			Parent = cardButton,
		}),
		Lock = label({
			Size = UDim2.fromScale(1, 1),
			BackgroundTransparency = 0.25,
			BackgroundColor3 = Color3.new(0, 0, 0),
			Text = `🔒\n{floorType.UnlockFloors} эт.`,
			ZIndex = 3,
			Parent = cardButton,
		}),
	}
	corner(10).Parent = card.Lock
	cards[i] = card
end

-- Уведомления
local toastList = create("Frame", {
	AnchorPoint = Vector2.new(0.5, 0),
	Position = UDim2.new(0.5, 0, 0.14, 8),
	Size = UDim2.new(0.5, 0, 0.3, 0),
	BackgroundTransparency = 1,
	Parent = gui,
}, {
	create("UIListLayout", {
		Padding = UDim.new(0, 4),
		HorizontalAlignment = Enum.HorizontalAlignment.Center,
		SortOrder = Enum.SortOrder.LayoutOrder,
	}),
})

---------------------------------------------------------------------
-- Окна: улучшения и подтверждение
---------------------------------------------------------------------
local function modal(title: string): (Frame, Frame, TextButton)
	local frame = create("Frame", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromScale(0.5, 0.6),
		BackgroundColor3 = COLORS.Panel,
		Visible = false,
		ZIndex = 10,
		Parent = gui,
	}, {
		corner(16),
		stroke(COLORS.Blue, 3),
		padding(10),
		create("UISizeConstraint", { MinSize = Vector2.new(300, 220), MaxSize = Vector2.new(620, 460) }),
	})
	label({
		Size = UDim2.new(1, -50, 0, 34),
		Text = title,
		TextXAlignment = Enum.TextXAlignment.Left,
		ZIndex = 11,
		Parent = frame,
	})
	local close = button({
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.fromScale(1, 0),
		Size = UDim2.fromOffset(40, 34),
		Text = "✕",
		ZIndex = 11,
		Parent = frame,
	}, COLORS.Red)
	local body = create("Frame", {
		Position = UDim2.new(0, 0, 0, 42),
		Size = UDim2.new(1, 0, 1, -42),
		BackgroundTransparency = 1,
		ZIndex = 11,
		Parent = frame,
	})
	close.Activated:Connect(function()
		frame.Visible = false
	end)
	return frame, body, close
end

local upgradesFrame, upgradesBody = modal("⬆️ Улучшения")
create("UIListLayout", {
	Padding = UDim.new(0, 8),
	SortOrder = Enum.SortOrder.LayoutOrder,
	Parent = upgradesBody,
})

type UpgradeRow = { Info: TextLabel, Buy: TextButton }
local upgradeRows: { [string]: UpgradeRow } = {}
local UPGRADE_ORDER = { "Stability", "Ads", "Manager" }

for order, name in UPGRADE_ORDER do
	local upgrade = Config.Upgrades[name]
	local row = create("Frame", {
		Size = UDim2.new(1, 0, 0.3, -6),
		BackgroundColor3 = COLORS.PanelLight,
		LayoutOrder = order,
		ZIndex = 11,
		Parent = upgradesBody,
	}, { corner(10), padding(6) })
	local info = label({
		Size = UDim2.fromScale(0.62, 1),
		Text = `{upgrade.Emoji} {upgrade.Name}\n{upgrade.Description}`,
		TextXAlignment = Enum.TextXAlignment.Left,
		ZIndex = 12,
		Parent = row,
	})
	local buy = button({
		AnchorPoint = Vector2.new(1, 0.5),
		Position = UDim2.fromScale(1, 0.5),
		Size = UDim2.fromScale(0.35, 0.8),
		Text = "💰 0",
		ZIndex = 12,
		Parent = row,
	}, COLORS.Green)
	buy.Activated:Connect(function()
		pop(buy)
		BuyUpgrade:FireServer(name)
	end)
	upgradeRows[name] = { Info = info, Buy = buy }
end

local confirmFrame, confirmBody = modal("♻️ Реконструкция")
local confirmText = label({
	Size = UDim2.fromScale(1, 0.62),
	Font = Enum.Font.Gotham,
	ZIndex = 12,
	Parent = confirmBody,
})
local confirmYes = button({
	Position = UDim2.fromScale(0, 0.7),
	Size = UDim2.fromScale(0.48, 0.3),
	Text = "Да, перестроить!",
	ZIndex = 12,
	Parent = confirmBody,
}, COLORS.Purple)
local confirmNo = button({
	Position = UDim2.fromScale(0.52, 0.7),
	Size = UDim2.fromScale(0.48, 0.3),
	Text = "Пока нет",
	ZIndex = 12,
	Parent = confirmBody,
}, COLORS.PanelLight)

---------------------------------------------------------------------
-- Состояние и обновление экрана
---------------------------------------------------------------------
local state: any = nil
local selectedIndex = 1

local function setSelected(index: number)
	selectedIndex = index
	for i, card in cards do
		card.Stroke.Color = if i == index then COLORS.Gold else Color3.fromRGB(70, 75, 100)
		card.Stroke.Thickness = if i == index then 3 else 2
	end
end
setSelected(1)

local function refresh()
	if not state then
		return
	end

	cashLabel.Text = `💰 {Format.Number(state.Cash)}`

	local safeColor = if state.Floors > state.SafeHeight then "#ff6b6b" else "#9aa0b9"
	local income = Format.Number(state.Income)
	local multiplier = string.format("%.2f", state.Multiplier)
	infoLabel.Text = `<font color="#5fd38a">+{income}/с</font>  •  🏢 {state.Floors} эт.  •  x{multiplier}  •  `
		.. `<font color="{safeColor}">🌪️ до {state.SafeHeight}</font>`

	registerPanel.Visible = not state.Manager
	registerLabel.Text = `🧾 Касса\n{Format.Number(state.Stored)}`

	-- карточки этажей
	for i, floorType in Config.FloorTypes do
		local card = cards[i]
		local unlocked = state.Floors >= floorType.UnlockFloors
		card.Lock.Visible = not unlocked
		card.Income.Text = `+{Format.Number(floorType.Income * state.Multiplier)}/с`
		local cost = state.FloorCosts[i]
		card.Cost.Text = `💰 {Format.Number(cost)}`
		card.Cost.TextColor3 = if state.Cash >= cost then COLORS.Gold else COLORS.Red
	end

	local selected = Config.FloorTypes[selectedIndex]
	local selectedCost = state.FloorCosts[selectedIndex]
	if state.Floors >= Config.MAX_FLOORS then
		buildButton.Text = "🏁 Максимальная высота!"
		buildButton.BackgroundColor3 = COLORS.PanelLight
	elseif state.Floors < selected.UnlockFloors then
		buildButton.Text = `🔒 {selected.Name}: нужно {selected.UnlockFloors} эт.`
		buildButton.BackgroundColor3 = COLORS.PanelLight
	else
		buildButton.Text = `🔨 {selected.Emoji} {selected.Name} — 💰 {Format.Number(selectedCost)}`
		buildButton.BackgroundColor3 = if state.Cash >= selectedCost then COLORS.Green else COLORS.PanelLight
	end

	-- ремонт
	repairButton.Visible = state.DamagedCount > 0
	repairButton.Text = `🔧 Ремонт {state.DamagedCount} эт.\n💰 {Format.Number(state.RepairCost)}`

	-- реконструкция
	local need = state.RebirthRequirement
	if state.Floors >= need then
		rebirthButton.Text = "♻️ Реконструкция ✅"
		rebirthButton.BackgroundColor3 = COLORS.Purple
	else
		rebirthButton.Text = `♻️ Реконструкция\n{state.Floors}/{need} эт.`
		rebirthButton.BackgroundColor3 = Color3.fromRGB(80, 60, 110)
	end

	passButton.Visible = Config.GAMEPASS_DOUBLE_INCOME ~= 0 and not state.DoubleIncome

	-- ежедневная награда
	dailyButton.Visible = state.DailyAvailable
	dailyButton.Text = `🎁 Награда\nдень {state.DailyStreak}`

	-- золотой час
	goldenLabel.Visible = state.GoldenLeft > 0
	if state.GoldenLeft > 0 then
		local left = state.GoldenLeft
		goldenLabel.Text = `✨ Золотой час x2 — {left // 60}:{string.format("%02d", left % 60)}`
	end

	-- уведомления всегда сразу под верхней панелью (и под плашкой золотого часа)
	local bottom = if goldenLabel.Visible then goldenLabel else statsPanel
	local y = bottom.AbsolutePosition.Y - gui.AbsolutePosition.Y + bottom.AbsoluteSize.Y + 8
	toastList.Position = UDim2.new(0.5, 0, 0, y)

	-- улучшения
	for name, row in upgradeRows do
		local upgrade = Config.Upgrades[name]
		local info = state.Upgrades[name]
		local extra = ""
		if name == "Stability" then
			extra = ` (сейчас: {state.SafeHeight} эт.)`
		elseif name == "Ads" then
			extra = ` (сейчас: +{math.floor(info.Level * Config.ADS_BONUS * 100 + 0.5)}%)`
		end
		local levelText = if upgrade.MaxLevel > 1 then ` ур. {info.Level}` else ""
		row.Info.Text = `{upgrade.Emoji} {upgrade.Name}{levelText}\n{upgrade.Description}{extra}`
		if info.Level >= info.MaxLevel then
			row.Buy.Text = if name == "Manager" then "Нанят ✅" else "МАКС ⭐"
			row.Buy.BackgroundColor3 = COLORS.PanelLight
		else
			row.Buy.Text = `💰 {Format.Number(info.Cost)}`
			row.Buy.BackgroundColor3 = if state.Cash >= info.Cost then COLORS.Green else COLORS.PanelLight
		end
	end
end

StateUpdate.OnClientEvent:Connect(function(newState)
	local previousFloors = if state then state.Floors else nil
	state = newState

	-- если открылся новый тип этажа, сразу выбираем его
	if previousFloors then
		for i, floorType in Config.FloorTypes do
			if previousFloors < floorType.UnlockFloors and state.Floors >= floorType.UnlockFloors then
				setSelected(i)
			end
		end
		if state.Floors > previousFloors then
			playSound(SOUND_BUILD, 0.4)
		end
		-- после реконструкции возвращаемся к первому этажу
		if state.Floors == 0 and previousFloors > 0 then
			setSelected(1)
		end
	else
		-- первый раз: выбираем лучший открытый этаж
		for i, floorType in Config.FloorTypes do
			if state.Floors >= floorType.UnlockFloors then
				setSelected(i)
			end
		end
	end
	refresh()
end)

---------------------------------------------------------------------
-- Уведомления и тряска при шторме
---------------------------------------------------------------------
local TOAST_COLORS = {
	info = COLORS.Blue,
	good = COLORS.Green,
	bad = COLORS.Red,
	money = COLORS.Gold,
	wind = COLORS.Orange,
	wind_warning = COLORS.Orange,
	golden = COLORS.Gold,
}

local toastCounter = 0
local function showToast(text: string, kind: string)
	toastCounter += 1
	local toasts = {}
	for _, child in toastList:GetChildren() do
		if child:IsA("Frame") then
			table.insert(toasts, child)
		end
	end
	-- не больше 4 уведомлений одновременно
	table.sort(toasts, function(a, b)
		return a.LayoutOrder < b.LayoutOrder
	end)
	while #toasts >= 4 do
		table.remove(toasts, 1):Destroy()
	end

	local toast = create("Frame", {
		Size = UDim2.new(1, 0, 0.22, 0),
		BackgroundColor3 = COLORS.Panel,
		BackgroundTransparency = 0.05,
		LayoutOrder = toastCounter,
		Parent = toastList,
	}, {
		corner(10),
		stroke(TOAST_COLORS[kind] or COLORS.Blue, 2),
		padding(4),
	})
	local text_ = label({ Size = UDim2.fromScale(1, 1), Text = text, Parent = toast })
	create("UITextSizeConstraint", { MaxTextSize = 22, Parent = text_ })
	pop(toast)

	task.delay(if kind == "wind_warning" then 6 else 3.5, function()
		if toast.Parent then
			local info = TweenInfo.new(0.4)
			TweenService:Create(toast, info, { BackgroundTransparency = 1 }):Play()
			TweenService:Create(text_, info, { TextTransparency = 1 }):Play()
			local toastStroke = toast:FindFirstChildOfClass("UIStroke")
			if toastStroke then
				TweenService:Create(toastStroke, info, { Transparency = 1 }):Play()
			end
			task.wait(0.45)
			toast:Destroy()
		end
	end)
end

local function shakeCamera(duration: number, strength: number)
	local character = player.Character
	local humanoid = character and character:FindFirstChildOfClass("Humanoid")
	if not humanoid then
		return
	end
	local started = os.clock()
	local connection
	connection = RunService.RenderStepped:Connect(function()
		local t = os.clock() - started
		if t > duration or not humanoid.Parent then
			humanoid.CameraOffset = Vector3.zero
			connection:Disconnect()
			return
		end
		local power = strength * (1 - t / duration)
		humanoid.CameraOffset = Vector3.new(
			(math.random() - 0.5) * power,
			(math.random() - 0.5) * power,
			(math.random() - 0.5) * power
		)
	end)
end

Notify.OnClientEvent:Connect(function(text, kind)
	showToast(text, kind)
	if kind == "money" or kind == "golden" then
		playSound(SOUND_MONEY, 0.5)
	elseif kind == "wind" then
		shakeCamera(1.5, 1.2)
	end
end)

---------------------------------------------------------------------
-- Кнопки
---------------------------------------------------------------------
for i, card in cards do
	card.Button.Activated:Connect(function()
		pop(card.Button)
		setSelected(i)
		refresh()
	end)
end

-- Строить можно нажатием или удержанием кнопки
local holding = false
local holdId = 0

local function buildOnce()
	BuildFloor:FireServer(Config.FloorTypes[selectedIndex].Id)
end

buildButton.MouseButton1Down:Connect(function()
	pop(buildButton)
	buildOnce()
	holding = true
	holdId += 1
	local myId = holdId
	task.delay(0.45, function()
		while holding and holdId == myId do
			buildOnce()
			task.wait(0.15)
		end
	end)
end)

local function stopHolding()
	holding = false
end
buildButton.MouseButton1Up:Connect(stopHolding)
buildButton.MouseLeave:Connect(stopHolding)
buildButton.InputEnded:Connect(function(input)
	if
		input.UserInputType == Enum.UserInputType.Touch
		or input.UserInputType == Enum.UserInputType.MouseButton1
	then
		stopHolding()
	end
end)

collectButton.Activated:Connect(function()
	pop(collectButton)
	Collect:FireServer()
end)

upgradesButton.Activated:Connect(function()
	pop(upgradesButton)
	confirmFrame.Visible = false
	upgradesFrame.Visible = not upgradesFrame.Visible
end)

repairButton.Activated:Connect(function()
	pop(repairButton)
	Repair:FireServer()
end)

rebirthButton.Activated:Connect(function()
	pop(rebirthButton)
	if not state then
		return
	end
	upgradesFrame.Visible = false
	if state.Floors < state.RebirthRequirement then
		showToast(`Нужно {state.RebirthRequirement} этажей для реконструкции`, "bad")
		return
	end
	local nextBonus = 1 + (state.Rebirths + 1) * Config.REBIRTH_BONUS
	confirmText.Text = `Башня, деньги и улучшения сбросятся.\nЗато доход навсегда станет x{string.format("%.1f", nextBonus)}!\nМенеджер останется.`
	confirmFrame.Visible = true
end)

confirmYes.Activated:Connect(function()
	confirmFrame.Visible = false
	Rebirth:FireServer()
end)
confirmNo.Activated:Connect(function()
	confirmFrame.Visible = false
end)

passButton.Activated:Connect(function()
	pop(passButton)
	if Config.GAMEPASS_DOUBLE_INCOME ~= 0 then
		MarketplaceService:PromptGamePassPurchase(player, Config.GAMEPASS_DOUBLE_INCOME)
	end
end)

dailyButton.Activated:Connect(function()
	pop(dailyButton)
	ClaimDaily:FireServer()
end)

-- Окно кодов
local codesFrame, codesBody = modal("🎟️ Коды")
local codeBox = create("TextBox", {
	Size = UDim2.fromScale(1, 0.35),
	BackgroundColor3 = COLORS.PanelLight,
	Font = Enum.Font.GothamBold,
	TextColor3 = COLORS.Text,
	PlaceholderText = "Введи код...",
	PlaceholderColor3 = COLORS.Muted,
	TextScaled = true,
	ClearTextOnFocus = false,
	Text = "",
	ZIndex = 12,
	Parent = codesBody,
}, { corner(10), padding(6) })
local codeHint = label({
	Position = UDim2.fromScale(0, 0.38),
	Size = UDim2.fromScale(1, 0.2),
	Font = Enum.Font.Gotham,
	TextColor3 = COLORS.Muted,
	Text = "Коды выходят в сообществе игры",
	ZIndex = 12,
	Parent = codesBody,
})
local redeemButton = button({
	Position = UDim2.fromScale(0, 0.64),
	Size = UDim2.fromScale(1, 0.34),
	Text = "Активировать",
	ZIndex = 12,
	Parent = codesBody,
}, COLORS.Green)

local function submitCode()
	if codeBox.Text ~= "" then
		RedeemCode:FireServer(codeBox.Text)
		codeBox.Text = ""
	end
end
redeemButton.Activated:Connect(function()
	pop(redeemButton)
	submitCode()
end)
codeBox.FocusLost:Connect(function(enterPressed)
	if enterPressed then
		submitCode()
	end
end)

codesButton.Activated:Connect(function()
	pop(codesButton)
	upgradesFrame.Visible = false
	confirmFrame.Visible = false
	codesFrame.Visible = not codesFrame.Visible
end)
-- окна не должны открываться одновременно
upgradesButton.Activated:Connect(function()
	codesFrame.Visible = false
end)

RequestState:FireServer()
