-- Создаёт участки игроков и строит башни из деталей.
-- Ничего заранее делать в Studio не нужно: всё появляется само при запуске.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Config"))
local Format = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Format"))

type FloorParts = {
	Body: BasePart,
	Windows: BasePart,
	Slab: BasePart,
}

export type Plot = {
	Index: number,
	Owner: Player?,
	CFrame: CFrame, -- центр верха участка, +Z локально = "лицом" к центру карты
	Model: Model,
	Tower: Model,
	Pad: BasePart,
	Roof: BasePart,
	SignLabel: TextLabel,
	RoofLabel: TextLabel,
	Floors: { FloorParts },
}

local TowerBuilder = {}

local plots: { Plot } = {}

local TOWER_OFFSET = Vector3.new(0, 0, -6) -- башня чуть в глубине участка
local DAMAGED_WINDOW = Color3.fromRGB(70, 25, 25)

local function makePart(props: { [string]: any }): Part
	local part = Instance.new("Part")
	part.Anchored = true
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	part.Material = Enum.Material.SmoothPlastic
	for key, value in pairs(props) do
		(part :: any)[key] = value
	end
	return part
end

local function makeSurfaceText(part: BasePart, face: Enum.NormalId, text: string, color: Color3): TextLabel
	local gui = Instance.new("SurfaceGui")
	gui.Face = face
	gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
	gui.PixelsPerStud = 40
	gui.Parent = part

	local label = Instance.new("TextLabel")
	label.Size = UDim2.fromScale(1, 1)
	label.BackgroundTransparency = 1
	label.TextScaled = true
	label.Font = Enum.Font.GothamBold
	label.TextColor3 = color
	label.Text = text
	label.Parent = gui
	return label
end

local function towerBaseCFrame(plot: Plot): CFrame
	return plot.CFrame * CFrame.new(TOWER_OFFSET)
end

local function floorBottomY(index: number): number
	return (index - 1) * Config.FLOOR_HEIGHT
end

local function moveRoof(plot: Plot)
	local floorCount = #plot.Floors
	local y = floorBottomY(floorCount + 1) + 0.5
	plot.Roof.CFrame = towerBaseCFrame(plot) * CFrame.new(0, y, 0)
	plot.Roof.Transparency = if floorCount == 0 then 1 else 0
	plot.Roof.CanCollide = floorCount > 0
	local antenna = plot.Roof:FindFirstChild("Antenna") :: BasePart?
	if antenna then
		antenna.CFrame = plot.Roof.CFrame * CFrame.new(0, 5.5, 0)
		antenna.Transparency = plot.Roof.Transparency
	end
end

local function updateLabels(plot: Plot)
	local owner = plot.Owner
	if owner then
		plot.SignLabel.Text = `🏢 {owner.DisplayName}`
		plot.RoofLabel.Text = `{owner.DisplayName}\n{Format.Number(#plot.Floors)} эт.`
	else
		plot.SignLabel.Text = "Свободный участок"
		plot.RoofLabel.Text = ""
	end
end

local function createPlot(index: number, origin: CFrame): Plot
	local model = Instance.new("Model")
	model.Name = "Plot" .. index

	local size = Config.PLOT_SIZE
	local base = makePart({
		Name = "Base",
		Size = Vector3.new(size, 1, size),
		CFrame = origin * CFrame.new(0, -0.5, 0),
		Material = Enum.Material.Concrete,
		Color = Color3.fromRGB(150, 150, 155),
		Parent = model,
	})

	-- дорожка от края к башне
	makePart({
		Name = "Path",
		Size = Vector3.new(8, 0.1, size / 2),
		CFrame = origin * CFrame.new(0, 0.05, size / 4),
		Color = Color3.fromRGB(90, 90, 95),
		Parent = model,
	})

	-- зелёная площадка "Собрать кассу"
	local pad = makePart({
		Name = "CollectPad",
		Size = Vector3.new(7, 0.4, 7),
		CFrame = origin * CFrame.new(13, 0.2, 13),
		Material = Enum.Material.Neon,
		Color = Color3.fromRGB(60, 220, 100),
		Parent = model,
	})
	makeSurfaceText(pad, Enum.NormalId.Top, "💰 СОБРАТЬ", Color3.fromRGB(20, 60, 20))

	-- табличка с именем владельца
	local sign = makePart({
		Name = "Sign",
		Size = Vector3.new(14, 4, 0.6),
		CFrame = origin * CFrame.new(-12, 3, size / 2 - 2),
		Color = Color3.fromRGB(40, 40, 50),
		Parent = model,
	})
	makePart({
		Name = "SignPost",
		Size = Vector3.new(0.6, 1, 0.6),
		CFrame = origin * CFrame.new(-12, 0.5, size / 2 - 2),
		Color = Color3.fromRGB(40, 40, 50),
		Parent = model,
	})
	-- Back = локальное +Z, то есть табличка смотрит к центру карты
	local signLabel = makeSurfaceText(sign, Enum.NormalId.Back, "Свободный участок", Color3.new(1, 1, 1))

	-- фундамент башни
	makePart({
		Name = "Foundation",
		Size = Vector3.new(Config.FLOOR_WIDTH + 4, 0.4, Config.FLOOR_WIDTH + 4),
		CFrame = origin * CFrame.new(TOWER_OFFSET) * CFrame.new(0, 0.2, 0),
		Material = Enum.Material.Slate,
		Color = Color3.fromRGB(70, 70, 75),
		Parent = model,
	})

	local tower = Instance.new("Model")
	tower.Name = "Tower"
	tower.Parent = model

	local roof = makePart({
		Name = "Roof",
		Size = Vector3.new(Config.FLOOR_WIDTH + 1, 1, Config.FLOOR_WIDTH + 1),
		Color = Color3.fromRGB(50, 50, 55),
		Transparency = 1,
		CanCollide = true,
		Parent = model,
	})
	makePart({
		Name = "Antenna",
		Size = Vector3.new(0.6, 10, 0.6),
		Material = Enum.Material.Neon,
		Color = Color3.fromRGB(255, 60, 60),
		Transparency = 1,
		CanCollide = false,
		Parent = roof,
	})

	local billboard = Instance.new("BillboardGui")
	billboard.Size = UDim2.fromOffset(220, 70)
	billboard.StudsOffset = Vector3.new(0, 14, 0)
	billboard.AlwaysOnTop = true
	billboard.MaxDistance = 2000
	billboard.Parent = roof

	local roofLabel = Instance.new("TextLabel")
	roofLabel.Size = UDim2.fromScale(1, 1)
	roofLabel.BackgroundTransparency = 1
	roofLabel.TextScaled = true
	roofLabel.Font = Enum.Font.GothamBold
	roofLabel.TextColor3 = Color3.new(1, 1, 1)
	roofLabel.TextStrokeTransparency = 0.3
	roofLabel.Text = ""
	roofLabel.Parent = billboard

	model.PrimaryPart = base
	model.Parent = workspace:FindFirstChild("Plots")

	local plot: Plot = {
		Index = index,
		Owner = nil,
		CFrame = origin,
		Model = model,
		Tower = tower,
		Pad = pad,
		Roof = roof,
		SignLabel = signLabel,
		RoofLabel = roofLabel,
		Floors = {},
	}
	moveRoof(plot)
	return plot
end

-- Создаёт все участки: два ряда, лицом друг к другу
function TowerBuilder.CreatePlots(): { Plot }
	local folder = workspace:FindFirstChild("Plots")
	if folder then
		folder:Destroy()
	end
	folder = Instance.new("Folder")
	folder.Name = "Plots"
	folder.Parent = workspace

	local perRow = math.ceil(Config.PLOT_COUNT / 2)
	local spacing = Config.PLOT_SPACING
	for index = 1, Config.PLOT_COUNT do
		local row = if index <= perRow then 0 else 1
		local column = (index - 1) % perRow
		local x = (column - (perRow - 1) / 2) * spacing
		local z = if row == 0 then -spacing / 2 else spacing / 2
		-- ряд 0 смотрит на +Z, ряд 1 развернут на 180°, чтобы тоже смотреть к центру
		local origin = CFrame.new(x, 0.01, z) * CFrame.Angles(0, if row == 0 then 0 else math.pi, 0)
		table.insert(plots, createPlot(index, origin))
	end
	return plots
end

function TowerBuilder.GetPlots(): { Plot }
	return plots
end

function TowerBuilder.GetPlot(player: Player): Plot?
	for _, plot in plots do
		if plot.Owner == player then
			return plot
		end
	end
	return nil
end

function TowerBuilder.ClaimPlot(player: Player): Plot?
	for _, plot in plots do
		if plot.Owner == nil then
			plot.Owner = player
			updateLabels(plot)
			return plot
		end
	end
	return nil
end

function TowerBuilder.ReleasePlot(player: Player)
	local plot = TowerBuilder.GetPlot(player)
	if plot then
		TowerBuilder.ClearTower(plot)
		plot.Owner = nil
		updateLabels(plot)
	end
end

-- Где появляется игрок: перед башней, лицом к ней
function TowerBuilder.GetSpawnCFrame(plot: Plot): CFrame
	local spawnPos = (plot.CFrame * CFrame.new(0, 4, Config.PLOT_SIZE / 2 - 6)).Position
	local lookAt = (towerBaseCFrame(plot) * CFrame.new(0, 4, 0)).Position
	return CFrame.lookAt(spawnPos, lookAt)
end

local function paintFloor(parts: FloorParts, typeId: number, damaged: boolean)
	local floorType = Config.GetFloorType(typeId) or Config.FloorTypes[1]
	if damaged then
		parts.Body.Color = floorType.Color:Lerp(Color3.new(0, 0, 0), 0.5)
		parts.Windows.Color = DAMAGED_WINDOW
		parts.Windows.Material = Enum.Material.SmoothPlastic
		if not parts.Body:FindFirstChild("Smoke") then
			local smoke = Instance.new("Smoke")
			smoke.Size = 3
			smoke.Opacity = 0.15
			smoke.RiseVelocity = 3
			smoke.Color = Color3.fromRGB(60, 60, 60)
			smoke.Parent = parts.Body
		end
	else
		parts.Body.Color = floorType.Color
		parts.Windows.Color = floorType.WindowColor
		parts.Windows.Material = Enum.Material.Glass
		local smoke = parts.Body:FindFirstChild("Smoke")
		if smoke then
			smoke:Destroy()
		end
	end
end

function TowerBuilder.AddFloor(plot: Plot, typeId: number, damaged: boolean?)
	local index = #plot.Floors + 1
	local base = towerBaseCFrame(plot)
	local bottom = floorBottomY(index)
	local width = Config.FLOOR_WIDTH
	local slabHeight = 0.8
	local bodyHeight = Config.FLOOR_HEIGHT - slabHeight

	local floorModel = Instance.new("Model")
	floorModel.Name = "Floor" .. index

	local slab = makePart({
		Name = "Slab",
		Size = Vector3.new(width + 1, slabHeight, width + 1),
		CFrame = base * CFrame.new(0, bottom + slabHeight / 2, 0),
		Material = Enum.Material.Concrete,
		Color = Color3.fromRGB(200, 200, 205),
		Parent = floorModel,
	})
	local body = makePart({
		Name = "Body",
		Size = Vector3.new(width, bodyHeight, width),
		CFrame = base * CFrame.new(0, bottom + slabHeight + bodyHeight / 2, 0),
		Parent = floorModel,
	})
	-- полоса окон чуть шире стены, поэтому видна со всех сторон
	local windows = makePart({
		Name = "Windows",
		Size = Vector3.new(width + 0.3, bodyHeight * 0.55, width + 0.3),
		CFrame = body.CFrame,
		Material = Enum.Material.Glass,
		Transparency = 0.1,
		CanCollide = false,
		Parent = floorModel,
	})

	local parts: FloorParts = { Body = body, Windows = windows, Slab = slab }
	paintFloor(parts, typeId, damaged == true)

	floorModel.Parent = plot.Tower
	table.insert(plot.Floors, parts)
	moveRoof(plot)
	updateLabels(plot)
end

function TowerBuilder.SetDamaged(plot: Plot, index: number, typeId: number, damaged: boolean)
	local parts = plot.Floors[index]
	if parts then
		paintFloor(parts, typeId, damaged)
	end
end

function TowerBuilder.ClearTower(plot: Plot)
	plot.Tower:ClearAllChildren()
	table.clear(plot.Floors)
	moveRoof(plot)
	updateLabels(plot)
end

-- Полностью перестраивает башню по сохранённым данным
function TowerBuilder.Rebuild(plot: Plot, floors: { number }, damaged: { number })
	TowerBuilder.ClearTower(plot)
	local damagedSet = {}
	for _, index in damaged do
		damagedSet[index] = true
	end
	for index, typeId in floors do
		TowerBuilder.AddFloor(plot, typeId, damagedSet[index] == true)
	end
end

return TowerBuilder
