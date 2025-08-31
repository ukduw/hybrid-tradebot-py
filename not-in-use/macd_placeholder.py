# line 160...

            if in_position:
                macd = get_latest_macd(symbol)
                percent_diff = ( macd['MACDh_12_26_9'] / macd['MACDs_12_26_9'] ) * 100 if macd['MACDs_12_26_9'] != 0 else 0
                macd_perc_high = None

                half_position = round(qty / 2)

                if price < stop: 
                    close_position(symbol, qty)
                    print(f"[{symbol}] STOP-LOSS hit. Exiting @ {price}")
                    async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                        await file.write(f"{now},{symbol},EXIT,{qty},{price}" + "\n")
                    pb.push_note("Hybrid bot", f"[{symbol}] STOP-LOSS hit. Exiting @ {price}")
                    return
                
                if 150 < percent_diff < 200: # TWEAK VALUES
                    macd_perc_high = percent_diff
                    while not percent_diff > 199:
                        macd = get_latest_macd(symbol)
                        percent_diff = ( macd['MACDh_12_26_9'] / macd['MACDs_12_26_9'] ) * 100
                        
                        if percent_diff > macd_perc_high:
                            macd_perc_high = percent_diff
                        if percent_diff <= macd_perc_high * 0.8: # TWEAK TRAIL
                            if not take_50:
                                take_50 = True
                                qty = qty - half_position
                                close_position(symbol, half_position)
                                print(f"[{symbol}] TAKE-PROFT hit. Exiting 50% position @ {price}")
                                async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                                    await file.write(f"{now}, {symbol}, 50% Exit, {half_position}, {price}" + "\n")
                                pb.push_note("Hybrid bot", f"[{symbol}] TAKE-PROFT hit. Exiting 50% position @ {price}")
                                break
                            else:
                                close_position(symbol, qty)
                                print(f"[{symbol}] TAKE-PROFT hit. 2nd Exiting 50% position @ {price}")
                                async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                                    await file.write(f"{now}, {symbol}, 2nd 50% Exit, {qty}, {price}" + "\n")
                                pb.push_note("Hybrid bot", f"[{symbol}] TAKE-PROFT hit. 2nd Exiting 50% position @ {price}")
                                return
                            
                        await asyncio.sleep(1)

                if percent_diff > 199: # TWEAK VALUE
                    macd_perc_high = percent_diff
                    while True:
                        macd = get_latest_macd(symbol)
                        percent_diff = ( macd['MACDh_12_26_9'] / macd['MACDs_12_26_9'] ) * 100

                        if percent_diff > macd_perc_high:
                            macd_perc_high = percent_diff
                        if percent_diff <= macd_perc_high * 0.8: # TWEAK TRAIL
                            close_position(symbol, qty)
                            print(f"[{symbol}] TAKE-PROFT hit. Exiting 100% position @ {price}")
                            async with aiofiles.open("trade-log/trade_log.txt", "a") as file:
                                await file.write(f"{now}, {symbol}, 100% Exit, {half_position}, {price}" + "\n")
                            pb.push_note("Hybrid bot", f"[{symbol}] TAKE-PROFT hit. Exiting 100% position @ {price}")
                            return
                        
                        await asyncio.sleep(1)
                
                await asyncio.sleep(1)
