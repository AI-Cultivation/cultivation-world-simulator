from typing import List, Dict, TYPE_CHECKING
import asyncio
from src.classes.gathering.gathering import Gathering, register_gathering
from src.classes.event import Event
from src.classes.story_event_service import StoryEventService
from src.classes.relation.relation_delta_service import RelationDeltaService
from src.utils.config import CONFIG
from src.utils.llm.client import call_llm_with_template
from src.utils.llm.runtime_mode import is_test_mode_enabled

if TYPE_CHECKING:
    from src.classes.core.world import World
    from src.classes.core.avatar import Avatar
    from src.classes.items.item import Item

@register_gathering
class Auction(Gathering):
    """
    拍卖会事件
    """
    
    # 类变量 - LLM Prompt
    STORY_PROMPT_ID = "auction_story_prompt"
    
    @classmethod
    def get_story_prompt(cls) -> str:
        """获取故事生成提示词"""
        from src.i18n import t
        return t(cls.STORY_PROMPT_ID)
    
    def is_start(self, world: "World") -> bool:
        """
        检测拍卖会是否开始
        条件：后台积攒的 sold_item_count 到达配置阈值
        """
        threshold = CONFIG.world.gathering.auction_trigger_count
        return world.circulation.sold_item_count >= threshold

    def get_related_avatars(self, world: "World") -> List[int]:
        """
        所有存活且允许参加聚会的 avatar 都参与
        """
        return [
            avatar.id 
            for avatar in world.avatar_manager.get_living_avatars()
            if self._can_avatar_join(avatar)
        ]

    def get_info(self, world: "World") -> str:
        from src.i18n import t
        return t("Auction is in progress...")

    async def get_needs(self, world: "World", avatars: List["Avatar"]) -> Dict["Item", Dict["Avatar", int]]:
        """
        获取所有参与角色对拍卖品的需程度
        返回格式: Dict[Item, Dict[Avatar, int]]
        """
        
        if is_test_mode_enabled():
            return {}

        # 1. 准备拍卖品信息
        items_info = []
        
        # 收集流通管理器中的物品
        circulation = world.circulation
        all_items = []
        all_items.extend(circulation.sold_weapons)
        all_items.extend(circulation.sold_auxiliaries)
        all_items.extend(circulation.sold_elixirs)
        
        for item in all_items:
            # 假设所有 item 都有 get_info 或类似方法
            # 这里统一用 get_detailed_info 如果有的话，或者 str(item)
            info = getattr(item, "get_detailed_info", lambda: str(item))()
            # 补充 ID 以便 LLM 引用
            items_info.append(f"ID: {item.id}, Info: {info}")
            
        items_str = "\n".join(items_info)
        
        # 2. 准备角色信息并分批处理
        batch_size = 5
        tasks = []
        
        for i in range(0, len(avatars), batch_size):
            batch_avatars = avatars[i : i + batch_size]
            
            # 构建该批次的 avatar_infos 字符串
            batch_infos = {}
            for avatar in batch_avatars:
                # 使用 avatar.get_info(detailed=True)
                info = avatar.get_info(detailed=True)
                batch_infos[avatar.name] = str(info)
            
            # 构建模板参数
            template_params = {
                "avatar_infos": str(batch_infos),
                "items": items_str
            }
            
            # 创建并发任务
            task = call_llm_with_template(
                template_path=CONFIG.paths.templates / "auction_need.txt",
                infos=template_params
            )
            tasks.append(task)
            
        # 3. 并发执行并收集结果
        results = await asyncio.gather(*tasks)
        
        # 4. 合并结果
        final_needs = {}
        for result in results:
            if isinstance(result, dict):
                final_needs.update(result)
                
        # 5. 转换结构为 dict[Item, dict[Avatar, int]]
        # 建立 name -> Avatar 映射
        name_to_avatar = {av.name: av for av in avatars}
        # 建立 id -> Item 映射
        id_to_item = {str(item.id): item for item in all_items}
        
        item_based_needs: Dict["Item", Dict["Avatar", int]] = {}
        
        # 遍历 final_needs: {avatar_name: {item_id: score}}
        for av_name, items_score_map in final_needs.items():
            avatar = name_to_avatar.get(av_name)
            if not avatar:
                continue
                
            for item_id, score in items_score_map.items():
                item = id_to_item.get(str(item_id))
                if not item:
                    continue
                    
                score_val = int(score)
                # 只有需求 > 1 才记录（可选优化，1表示完全不需要）
                if score_val <= 1:
                    continue
                    
                if item not in item_based_needs:
                    item_based_needs[item] = {}
                item_based_needs[item][avatar] = score_val
                
        return item_based_needs

    def _calculate_bid(self, item: "Item", need_level: int, current_balance: int) -> int:
        """
        计算单次出价，根据当前余额动态调整
        """
        from src.classes.prices import prices
        
        if need_level <= 1:
            return 0
            
        # 策略：
        # Need 2: min(money, base_price * 0.8)  (捡漏)
        # Need 3: min(money, base_price * 1.5)  (略微溢价)
        # Need 4: min(money, base_price * 3.0)  (高倍溢价)
        # Need 5: money                         (梭哈)
        
        base_price = prices.get_price(item)
        multipliers = {
            2: 0.8,
            3: 1.5,
            4: 3.0,
        }
        
        if need_level >= 5:
            return current_balance
        
        multiplier = multipliers.get(need_level, 0.0)
        calculated_price = int(base_price * multiplier)
        
        # 最终出价不能超过当前余额
        return min(current_balance, calculated_price)

    def resolve_auctions(
        self,
        needs: Dict["Item", Dict["Avatar", int]]
    ) -> tuple[Dict["Item", tuple["Avatar", int]], List["Item"], Dict["Item", Dict["Avatar", int]]]:
        """
        结算拍卖结果
        Returns:
            deal_results: 成交结果 {item: (winner, price)}
            unsold_items: 流拍物品列表
            all_willing_prices: 所有的出价记录 {item: {avatar: price}} (用于生成故事)
        """
        from src.classes.prices import prices

        deal_results = {}
        unsold_items = []
        all_willing_prices = {} 
        
        # 1. 建立角色资金快照
        all_avatars = set()
        for av_map in needs.values():
            all_avatars.update(av_map.keys())
        current_balances = {av: int(av.magic_stone) for av in all_avatars}
        
        # 2. 物品排序：按价值从高到低结算，优先处理贵重物品
        sorted_items = sorted(needs.keys(), key=lambda x: prices.get_price(x), reverse=True)
        
        for item in sorted_items:
            avatar_needs = needs[item]
            bids = {}
            
            # 计算该物品的所有有效出价
            for avatar, need_val in avatar_needs.items():
                balance = current_balances.get(avatar, 0)
                if balance <= 0:
                    continue
                    
                bid = self._calculate_bid(item, need_val, balance)
                if bid > 0:
                    bids[avatar] = bid
            
            if bids:
                all_willing_prices[item] = bids
            
            # 判定流拍
            if not bids:
                unsold_items.append(item)
                continue
            
            # 判定赢家 (第二价格密封拍卖)
            sorted_bids = sorted(bids.items(), key=lambda x: x[1], reverse=True)
            winner, highest_bid = sorted_bids[0]
            
            deal_price = 0
            if len(sorted_bids) >= 2:
                second_bid = sorted_bids[1][1]
                deal_price = min(highest_bid, second_bid + 1)
            else:
                # 无竞争：底价成交 (60% bid)
                deal_price = max(1, int(highest_bid * 0.6))
            
            # 只有成交价 <= 余额时才有效（理论上 calculate_bid 已经保证了 bid <= balance，
            # 但为了逻辑闭环，且 bid >= deal_price，所以 deal_price <= balance 必然成立）
            
            # 更新状态
            current_balances[winner] -= deal_price
            deal_results[item] = (winner, deal_price)
            
        return deal_results, unsold_items, all_willing_prices

    def _generate_auction_events(
        self,
        world: "World",
        deal_results: Dict["Item", tuple["Avatar", int]],
        willing_prices: Dict["Item", Dict["Avatar", int]]
    ) -> List[Event]:
        """
        生成拍卖事件（合并成交与竞争信息）
        """
        from src.i18n import t
        events = []
        month_stamp = world.month_stamp
        
        for item, (winner, deal_price) in deal_results.items():
            bids = willing_prices.get(item, {})
            # 检查是否有竞争者（出价人数 >= 2）
            if len(bids) >= 2:
                # 获取出价第二名
                sorted_bids = sorted(bids.items(), key=lambda x: x[1], reverse=True)
                runner_up = sorted_bids[1][0]
                
                content = t(
                    "In the auction for {item_name}, {winner_name} outbid {runner_up_name} with {price} spirit stones and won the item.",
                    item_name=item.name,
                    winner_name=winner.name,
                    runner_up_name=runner_up.name,
                    price=deal_price
                )
                related_avatars = [winner.id, runner_up.id]
            else:
                content = t(
                    "At the auction, {winner_name} acquired {item_name} for {price} spirit stones.",
                    winner_name=winner.name,
                    item_name=item.name,
                    price=deal_price
                )
                related_avatars = [winner.id]
                
            event = Event(
                month_stamp=month_stamp,
                content=content,
                related_avatars=related_avatars,
                is_major=False
            )
            if len(related_avatars) >= 2:
                runner_up_avatar = world.avatar_manager.get_avatar(related_avatars[1])
                if runner_up_avatar is not None:
                    winner_avatar = world.avatar_manager.get_avatar(related_avatars[0])
                    if winner_avatar is not None:
                        mode = RelationDeltaService.get_action_mode("gathering")
                        if mode == "llm":
                            # gathering 结算点是同步函数，统一在 execute 末尾异步补 delta
                            setattr(event, "_relation_delta_pair", (winner_avatar, runner_up_avatar))
            events.append(event)
            
        return events

    async def _generate_story(
        self,
        world: "World",
        deal_results: Dict["Item", tuple["Avatar", int]],
        willing_prices: Dict["Item", Dict["Avatar", int]]
    ) -> List[Event]:
        """
        生成故事 (StoryTeller)
        将本次拍卖的所有重要信息（成交、竞争）汇总传给 LLM，
        让 LLM 自行选取切入点生成故事。
        """
        from src.i18n import t
        events = []
        
        # 1. 收集所有相关事件文本
        interaction_lines = []
        
        # 收集成交信息
        for item, (winner, deal_price) in deal_results.items():
            interaction_lines.append(
                t("Deal: {winner_name} acquired {item_name} for {price} spirit stones.",
                  winner_name=winner.name, item_name=item.name, price=deal_price)
            )
            
        # 收集竞争信息（压一头）
        # 这里为了避免重复太琐碎，只记录竞争激烈（参与者>=2）的情况
        rivalry_avatars = set()
        for item, bids in willing_prices.items():
            if len(bids) < 2:
                continue
            sorted_bids = sorted(bids.items(), key=lambda x: x[1], reverse=True)
            winner = sorted_bids[0][0]
            runner_up = sorted_bids[1][0]
            interaction_lines.append(
                t("Competition: In the auction for {item_name}, {winner_name} outbid {runner_up_name} (bid: {bid}).",
                  item_name=item.name, winner_name=winner.name, 
                  runner_up_name=runner_up.name, bid=sorted_bids[1][1])
            )
            rivalry_avatars.add(winner)
            rivalry_avatars.add(runner_up)
            
        if not interaction_lines:
            return []
            
        interaction_result = "\n".join(interaction_lines)
        
        # 2. 收集相关 items 信息
        # 只收集成交了的或者有竞争的物品
        related_items = set(deal_results.keys())
        for item in willing_prices:
            if len(willing_prices[item]) >= 2:
                related_items.add(item)
                
        items_info_list = []
        for item in related_items:
            info = getattr(item, "get_detailed_info", lambda: str(item))()
            items_info_list.append(
                t("Item: {item_name}, Description: {description}",
                  item_name=item.name, description=info)
            )
        items_info_str = "\n".join(items_info_list)
        
        # 3. 收集相关 avatars
        # 主要是成交者和有明显竞争行为的
        related_avatars = set()
        for winner, _ in deal_results.values():
            related_avatars.add(winner)
        related_avatars.update(rivalry_avatars)
        
        if not related_avatars:
            return []

        # 4. 调用 StoryTeller
        # 准备模板参数
        gathering_info = t(
            "Event Type: Mysterious Auction\nScene Setting: The auction takes place in a mysterious space, hosted by a mysterious figure with an unfathomable aura."
        )
        
        # 构建 details (物品信息 + 角色信息)
        # 物品信息
        details_list = []
        if items_info_str:
            details_list.append(t("【Auction Items Information】"))
            details_list.append(items_info_str)
            
        # 角色信息
        details_list.append(t("\n【Related Avatars Information】"))
        for av in related_avatars:
            # 获取详细信息
            info = av.get_info(detailed=True)
            details_list.append(f"- {av.name}: {info}")
            
        details_text = "\n".join(details_list)
        
        story_event = await StoryEventService.maybe_create_gathering_story(
            month_stamp=world.month_stamp,
            gathering_info=gathering_info,
            events_text=interaction_result,
            details_text=details_text,
            related_avatars=list(related_avatars),
            prompt=self.get_story_prompt(),
        )
        if story_event is not None:
            events.append(story_event)
        
        return events

    async def execute(self, world: "World") -> List[Event]:
        """
        执行拍卖会
        """
        events = []
        
        # 0. 检查是否有物品
        # 只要 sold_item_count >= threshold 就已经保证有物品了，但为了安全再检查一次
        if world.circulation.sold_item_count == 0:
            return []
            
        avatars = [world.avatar_manager.get_avatar(aid) for aid in self.get_related_avatars(world)]
        # 过滤掉 None
        avatars = [a for a in avatars if a]
        
        if not avatars:
            return []

        # 1. 计算需求
        needs = await self.get_needs(world, avatars)
        
        # 2. 结算拍卖 (动态计算出价，处理资产穿透)
        deal_results, unsold_items, willing_prices = self.resolve_auctions(needs)
        
        # 3. 执行交易 (扣钱、给物品、移除 circulation)
        from src.classes.items.weapon import Weapon
        from src.classes.items.auxiliary import Auxiliary
        from src.classes.items.elixir import Elixir
        from src.classes.material import Material
        from src.classes.prices import prices
        
        # 处理成交物品
        for item, (winner, price) in deal_results.items():
            # 扣钱
            winner.magic_stone -= price
            
            # 移除 circulation (先移除，避免因为交换装备导致的添加逻辑混淆)
            world.circulation.remove_item(item)
            
            # 给物品
            if isinstance(item, (Weapon, Auxiliary)):
                # 装备并处理旧装备
                # 特殊逻辑：拍卖会换下的旧装备直接销毁（折价回收但不再进入流通池），防止物品无限膨胀
                
                if isinstance(item, Weapon):
                    old_equip = winner.weapon
                    if old_equip:
                        # 计算回收价
                        refund = prices.get_selling_price(old_equip, winner)
                        winner.magic_stone += refund
                    # 换装
                    winner.change_weapon(item)
                    
                elif isinstance(item, Auxiliary):
                    old_equip = winner.auxiliary
                    if old_equip:
                        refund = prices.get_selling_price(old_equip, winner)
                        winner.magic_stone += refund
                    # 换装
                    winner.change_auxiliary(item)
                
            elif isinstance(item, Elixir):
                # 丹药直接服用
                winner.consume_elixir(item)
                
            elif isinstance(item, Material):
                # 材料放入背包
                winner.add_material(item)
        
        # 处理流拍物品：直接销毁（移出流通池）
        for item in unsold_items:
            world.circulation.remove_item(item)
            
        # 5. 生成基础事件（合并成交与竞争信息）
        auction_events = self._generate_auction_events(world, deal_results, willing_prices)
        events.extend(auction_events)
        for event in auction_events:
            pair = getattr(event, "_relation_delta_pair", None)
            if pair is None:
                continue
            winner_avatar, runner_up_avatar = pair
            a_to_b, b_to_a = await RelationDeltaService.resolve_event_text_delta(
                action_key="gathering",
                avatar_a=winner_avatar,
                avatar_b=runner_up_avatar,
                event_text=event.content,
            )
            RelationDeltaService.apply_bidirectional_delta(winner_avatar, runner_up_avatar, a_to_b, b_to_a)

        # 6. 生成故事 (StoryTeller)
        story_events = await self._generate_story(world, deal_results, willing_prices)
        events.extend(story_events)
        
        return events
